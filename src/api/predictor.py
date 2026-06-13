import os
import re
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from xgboost import XGBRegressor
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Path setup
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS_DIR = os.path.join(BASE_DIR, "models")

class DelayPredictor:
    def __init__(self):
        self.db_engine = self._get_db_engine()
        self.dep_model, self.dep_meta = self._load_model_and_meta("departure_delay_xgb")
        self.arr_model, self.arr_meta = self._load_model_and_meta("arrival_delay_xgb")

    def _get_db_engine(self):
        """Creates a database engine using the environment configurations."""
        load_dotenv(os.path.join(BASE_DIR, ".env"))
        db_type = os.getenv("DB_TYPE", "sqlite").lower()

        if db_type == "mysql":
            user = os.getenv("DB_USER", "root")
            password = os.getenv("DB_PASSWORD", "")
            host = os.getenv("DB_HOST", "localhost")
            port = os.getenv("DB_PORT", "3306")
            name = os.getenv("DB_NAME", "sbb_delays")
            db_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{name}"
        else:
            sqlite_path = os.getenv("SQLITE_PATH", "data/sbb_delays.db")
            db_url = f"sqlite:///{sqlite_path}"

        return create_engine(db_url)

    def _load_model_and_meta(self, model_name: str) -> Tuple[Optional[XGBRegressor], Optional[Dict[str, Any]]]:
        """Loads a model and its metadata from the models directory."""
        model_path = os.path.join(MODELS_DIR, f"{model_name}.json")
        meta_path = os.path.join(MODELS_DIR, f"{model_name}_metadata.json")

        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            print(f"[WARN] Model or metadata files missing for {model_name}")
            return None, None

        try:
            # Load metadata
            with open(meta_path, "r") as f:
                meta = json.load(f)

            # Initialize and load XGBoost Regressor
            model = XGBRegressor()
            model.load_model(model_path)
            
            print(f"[OK] Successfully loaded {model_name}")
            return model, meta
        except Exception as e:
            print(f"[ERROR] Failed to load {model_name}: {e}")
            return None, None

    def reload_models(self) -> Dict[str, str]:
        """Reloads the models and metadata from disk."""
        self.dep_model, self.dep_meta = self._load_model_and_meta("departure_delay_xgb")
        self.arr_model, self.arr_meta = self._load_model_and_meta("arrival_delay_xgb")
        return {
            "departure_model": "Success" if self.dep_model else "Failed",
            "arrival_model": "Success" if self.arr_model else "Failed"
        }

    def get_station_name(self, station_uic: str) -> Optional[str]:
        """Retrieves the station name from the database metadata."""
        try:
            with self.db_engine.connect() as conn:
                query = text("SELECT name FROM stations WHERE uic_code = :uic")
                res = conn.execute(query, {"uic": station_uic}).fetchone()
                return res[0] if res else None
        except Exception as e:
            print(f"[DB ERROR] Failed to fetch station name: {e}")
            return None

    def _query_station_lag_delays(self, station_uic: str) -> Tuple[float, float]:
        """Queries the last 3 trains at a station to calculate rolling delay averages."""
        try:
            with self.db_engine.connect() as conn:
                dep_query = text("""
                    SELECT departure_delay_min 
                    FROM trips 
                    WHERE station_uic = :station_uic AND departure_delay_min IS NOT NULL 
                    ORDER BY scheduled_departure DESC 
                    LIMIT 3
                """)
                dep_res = conn.execute(dep_query, {"station_uic": station_uic}).fetchall()
                avg_dep = np.mean([r[0] for r in dep_res]) if dep_res else 0.0

                arr_query = text("""
                    SELECT arrival_delay_min 
                    FROM trips 
                    WHERE station_uic = :station_uic AND arrival_delay_min IS NOT NULL 
                    ORDER BY scheduled_arrival DESC 
                    LIMIT 3
                """)
                arr_res = conn.execute(arr_query, {"station_uic": station_uic}).fetchall()
                avg_arr = np.mean([r[0] for r in arr_res]) if arr_res else 0.0
                
                return float(avg_dep), float(avg_arr)
        except Exception as e:
            print(f"[DB ERROR] Failed to query rolling delays: {e}")
            return 0.0, 0.0

    def _query_route_hour_avg_delays(self, linien_text: str, hour_of_day: int) -> Tuple[float, float]:
        """Queries historical average delays for a route and hour in a database-agnostic way."""
        try:
            with self.db_engine.connect() as conn:
                query = text("""
                    SELECT scheduled_departure, departure_delay_min, scheduled_arrival, arrival_delay_min 
                    FROM trips 
                    WHERE linien_text = :linien_text
                """)
                rows = conn.execute(query, {"linien_text": linien_text}).fetchall()
                
                if not rows:
                    return 0.0, 0.0

                dep_delays = []
                arr_delays = []
                
                for scheduled_dep, dep_delay, scheduled_arr, arr_delay in rows:
                    if scheduled_dep and dep_delay is not None:
                        dt = datetime.fromisoformat(scheduled_dep) if isinstance(scheduled_dep, str) else scheduled_dep
                        if dt.hour == hour_of_day:
                            dep_delays.append(dep_delay)
                    if scheduled_arr and arr_delay is not None:
                        dt = datetime.fromisoformat(scheduled_arr) if isinstance(scheduled_arr, str) else scheduled_arr
                        if dt.hour == hour_of_day:
                            arr_delays.append(arr_delay)

                avg_dep = np.mean(dep_delays) if dep_delays else 0.0
                avg_arr = np.mean(arr_delays) if arr_delays else 0.0
                return float(avg_dep), float(avg_arr)
        except Exception as e:
            print(f"[DB ERROR] Failed to query route hour averages: {e}")
            return 0.0, 0.0

    def construct_features(self, request_data: Dict[str, Any], is_arrival: bool = False) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Processes raw inputs and performs feature engineering, querying the DB for fallbacks if necessary.
        Returns the final 1x32 numpy array and a dictionary of the actual features used.
        """
        meta = self.arr_meta if is_arrival else self.dep_meta
        if not meta:
            raise ValueError("Model metadata is not loaded.")
        
        feature_names = meta["feature_names"]

        # Parse schedule time
        sched_time = request_data["scheduled_time"]
        if isinstance(sched_time, str):
            sched_time = datetime.fromisoformat(sched_time)

        # 1. Temporal Features
        hour_of_day = sched_time.hour
        day_of_week = sched_time.weekday()
        month = sched_time.month
        is_weekend = 1 if day_of_week >= 5 else 0
        is_rush_hour = 1 if (7 <= hour_of_day <= 9 or 16 <= hour_of_day <= 18) else 0

        # Cyclical Temporal features
        hour_sin = np.sin(2 * np.pi * hour_of_day / 24)
        hour_cos = np.cos(2 * np.pi * hour_of_day / 24)
        month_sin = np.sin(2 * np.pi * month / 12)
        month_cos = np.cos(2 * np.pi * month / 12)

        # Weather features (default to fallback values if missing)
        temp_c = request_data.get("temperature_c")
        precip_mm = request_data.get("precipitation_mm")
        snow_depth = request_data.get("snow_depth_cm")
        w_code = request_data.get("weather_code")

        temp_c = 15.0 if temp_c is None else temp_c
        precip_mm = 0.0 if precip_mm is None else precip_mm
        snow_depth = 0.0 if snow_depth is None else snow_depth
        w_code = 0 if w_code is None else w_code

        # Same train origin departure delay (default to 0.0 if missing)
        origin_dep_delay = request_data.get("origin_departure_delay")
        origin_dep_delay = 0.0 if origin_dep_delay is None else origin_dep_delay

        # Station rolling lag delays (query DB if missing)
        station_avg_dep = request_data.get("station_avg_delay_last_3")
        station_avg_arr = request_data.get("station_avg_arr_delay_last_3")
        if station_avg_dep is None or station_avg_arr is None:
            db_dep, db_arr = self._query_station_lag_delays(request_data["station_uic"])
            station_avg_dep = db_dep if station_avg_dep is None else station_avg_dep
            station_avg_arr = db_arr if station_avg_arr is None else station_avg_arr

        # Historical route/hour delays (query DB if missing)
        route_hour_dep = request_data.get("route_hour_avg_delay")
        route_hour_arr = request_data.get("route_hour_avg_arr_delay")
        if route_hour_dep is None or route_hour_arr is None:
            db_rh_dep, db_rh_arr = self._query_route_hour_avg_delays(request_data["linien_text"], hour_of_day)
            route_hour_dep = db_rh_dep if route_hour_dep is None else route_hour_dep
            route_hour_arr = db_rh_arr if route_hour_arr is None else route_hour_arr

        # Build base numeric feature dictionary
        features = {
            "hour_of_day": float(hour_of_day),
            "day_of_week": float(day_of_week),
            "month": float(month),
            "is_weekend": float(is_weekend),
            "is_rush_hour": float(is_rush_hour),
            "hour_sin": float(hour_sin),
            "hour_cos": float(hour_cos),
            "month_sin": float(month_sin),
            "month_cos": float(month_cos),
            "temperature_c": float(temp_c),
            "precipitation_mm": float(precip_mm),
            "snow_depth_cm": float(snow_depth),
            "weather_code": float(w_code),
            "origin_departure_delay": float(origin_dep_delay),
            "station_avg_delay_last_3": float(station_avg_dep),
            "station_avg_arr_delay_last_3": float(station_avg_arr),
            "route_hour_avg_delay": float(route_hour_dep),
            "route_hour_avg_arr_delay": float(route_hour_arr),
        }

        # Train type extraction
        linien_text = request_data["linien_text"]
        train_type_match = re.match(r"([A-Z]+)", linien_text)
        train_type = train_type_match.group(1) if train_type_match else "OTHER"

        # Apply one-hot encoding values based on metadata configuration
        for col in feature_names:
            if col.startswith("station_uic_"):
                uic_val = col.split("station_uic_")[1]
                features[col] = 1.0 if request_data["station_uic"] == uic_val else 0.0
            elif col.startswith("linien_text_"):
                line_val = col.split("linien_text_")[1]
                features[col] = 1.0 if linien_text == line_val else 0.0
            elif col.startswith("train_type_"):
                type_val = col.split("train_type_")[1]
                features[col] = 1.0 if train_type == type_val else 0.0

        # Construct final numpy feature array in exact order
        feature_vector = []
        for name in feature_names:
            feature_vector.append(features.get(name, 0.0))

        X = np.array(feature_vector).reshape(1, -1)
        return X, features

    def predict_departure(self, request_data: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """Predicts departure delay in minutes."""
        if not self.dep_model:
            raise RuntimeError("Departure model is not loaded.")
        
        X, features = self.construct_features(request_data, is_arrival=False)
        pred = self.dep_model.predict(X)[0]
        # Clip negative predictions to 0
        pred = float(np.clip(pred, 0.0, None))
        return pred, features

    def predict_arrival(self, request_data: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """Predicts arrival delay in minutes."""
        if not self.arr_model:
            raise RuntimeError("Arrival model is not loaded.")
        
        X, features = self.construct_features(request_data, is_arrival=True)
        pred = self.arr_model.predict(X)[0]
        # Clip negative predictions to 0
        pred = float(np.clip(pred, 0.0, None))
        return pred, features
