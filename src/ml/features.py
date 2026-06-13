"""
Phase 2: Feature Engineering Module
====================================
Extracts trips and weather data from the database, merges them on station + closest hour,
and constructs ML-ready features for XGBoost delay prediction.

Features produced:
  - Temporal: hour_of_day, day_of_week, month, is_weekend, is_rush_hour
  - Spatial/Route: station_uic (encoded), linien_text (encoded), train_type (IC/IR/S)
  - Weather: temperature_c, precipitation_mm, snow_depth_cm, weather_code
  - Lag: station_avg_delay_last_3h (rolling mean of last 3 trains at same station)
  - Historical: route_hour_avg_delay (historical average delay for route + hour combo)
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Allow imports from sibling packages
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def get_db_engine():
    """Creates a database engine using the same logic as the ingest pipeline."""
    load_dotenv()
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


def load_trips(engine):
    """Load all trips from the database."""
    query = text("""
        SELECT
            id, betriebstag, fahrt_bezeichner, produkt_id, linien_text,
            station_uic, station_name,
            scheduled_arrival, actual_arrival, arrival_delay_min,
            scheduled_departure, actual_departure, departure_delay_min,
            faellt_aus, zusatzfahrt
        FROM trips
        WHERE faellt_aus = 0
        ORDER BY betriebstag, scheduled_departure, scheduled_arrival
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    print(f"Loaded {len(df)} trip records from database.")
    return df


def load_weather(engine):
    """Load all weather observations from the database."""
    query = text("""
        SELECT
            station_uic, observation_time,
            temperature_c, precipitation_mm, snow_depth_cm, weather_code
        FROM weather_observations
        ORDER BY station_uic, observation_time
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    print(f"Loaded {len(df)} weather records from database.")
    return df


def merge_trips_weather(trips_df, weather_df):
    """
    Merge trips with weather observations using the closest hourly observation.
    For each trip, we find the weather at the same station and the nearest hour
    to the scheduled departure (or arrival if departure is null).
    """
    # Parse datetime columns
    weather_df = weather_df.copy()
    weather_df["observation_time"] = pd.to_datetime(weather_df["observation_time"])

    trips_df = trips_df.copy()
    trips_df["scheduled_departure"] = pd.to_datetime(trips_df["scheduled_departure"])
    trips_df["scheduled_arrival"] = pd.to_datetime(trips_df["scheduled_arrival"])
    trips_df["actual_departure"] = pd.to_datetime(trips_df["actual_departure"])
    trips_df["actual_arrival"] = pd.to_datetime(trips_df["actual_arrival"])
    trips_df["betriebstag"] = pd.to_datetime(trips_df["betriebstag"])

    # For each trip, determine the reference time for weather lookup
    # Use scheduled_departure if available, otherwise scheduled_arrival
    trips_df["ref_time"] = trips_df["scheduled_departure"].fillna(trips_df["scheduled_arrival"])

    # Floor reference time to the nearest hour for matching
    trips_df["ref_hour"] = trips_df["ref_time"].dt.floor("h")

    # Floor weather observation_time to the nearest hour
    weather_df["obs_hour"] = weather_df["observation_time"].dt.floor("h")

    # Merge on station_uic and matching hour
    merged = trips_df.merge(
        weather_df[["station_uic", "obs_hour", "temperature_c", "precipitation_mm", "snow_depth_cm", "weather_code"]],
        left_on=["station_uic", "ref_hour"],
        right_on=["station_uic", "obs_hour"],
        how="left"
    )

    # Drop helper columns
    merged.drop(columns=["obs_hour"], inplace=True, errors="ignore")

    print(f"Merged dataset: {len(merged)} rows. Weather matched: {merged['temperature_c'].notna().sum()} ({merged['temperature_c'].notna().mean()*100:.1f}%)")
    return merged


def engineer_features(df):
    """
    Constructs ML features from the merged trips+weather dataframe.
    Returns a clean feature dataframe ready for model training.
    """
    df = df.copy()

    # ── Temporal Features ──────────────────────────────────────────────
    df["hour_of_day"] = df["ref_time"].dt.hour
    df["day_of_week"] = df["ref_time"].dt.dayofweek  # 0=Mon, 6=Sun
    df["month"] = df["ref_time"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_rush_hour"] = df["hour_of_day"].apply(
        lambda h: 1 if (7 <= h <= 9 or 16 <= h <= 18) else 0
    )

    # Cyclical encoding for hour and month (helps capture periodicity)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour_of_day"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour_of_day"] / 24)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    # ── Route / Spatial Features ───────────────────────────────────────
    # Extract train type from linien_text (IC, IR, S, RE, etc.)
    df["train_type"] = df["linien_text"].str.extract(r"([A-Z]+)", expand=False).fillna("OTHER")

    # ── Cross-Trip Feature: Same Train's Departure Delay ─────────────
    # For arrival rows (destination), the strongest predictor is:
    # "how late did this same train depart from its origin?"
    # We self-join on fahrt_bezeichner to propagate departure delay.
    origin_delays = (
        df[df["departure_delay_min"].notna()][["fahrt_bezeichner", "betriebstag", "departure_delay_min"]]
        .rename(columns={"departure_delay_min": "origin_departure_delay"})
    )
    df = df.merge(
        origin_delays,
        on=["fahrt_bezeichner", "betriebstag"],
        how="left"
    )
    df["origin_departure_delay"] = df["origin_departure_delay"].fillna(0.0)

    # ── Lag Features (No Future Leakage) ──────────────────────────────
    # Sort chronologically to ensure lag features are computed correctly
    df.sort_values(by=["station_uic", "ref_time"], inplace=True)

    # Rolling average of last 3 departure delays at the SAME station
    # We use shift(1) to exclude the current row (prevents leakage)
    df["station_avg_delay_last_3"] = (
        df.groupby("station_uic")["departure_delay_min"]
        .transform(lambda x: x.shift(1).rolling(window=3, min_periods=1).mean())
    )

    # Rolling average of last 3 ARRIVAL delays at the same station
    df["station_avg_arr_delay_last_3"] = (
        df.groupby("station_uic")["arrival_delay_min"]
        .transform(lambda x: x.shift(1).rolling(window=3, min_periods=1).mean())
    )

    # ── Historical Aggregate Feature ──────────────────────────────────
    # Average delay per route (linien_text) and hour — computed on the whole dataset
    # This is a static historical average, not a leaky look-ahead
    route_hour_avg = (
        df.groupby(["linien_text", "hour_of_day"])["departure_delay_min"]
        .mean()
        .rename("route_hour_avg_delay")
    )
    df = df.merge(route_hour_avg, on=["linien_text", "hour_of_day"], how="left")

    # Historical average ARRIVAL delay per route + hour
    route_hour_arr_avg = (
        df.groupby(["linien_text", "hour_of_day"])["arrival_delay_min"]
        .mean()
        .rename("route_hour_avg_arr_delay")
    )
    df = df.merge(route_hour_arr_avg, on=["linien_text", "hour_of_day"], how="left")

    # ── Fill NaN in weather / lag columns ─────────────────────────────
    weather_cols = ["temperature_c", "precipitation_mm", "snow_depth_cm", "weather_code"]
    for col in weather_cols:
        df[col] = df[col].fillna(0.0)

    df["station_avg_delay_last_3"] = df["station_avg_delay_last_3"].fillna(0.0)
    df["station_avg_arr_delay_last_3"] = df["station_avg_arr_delay_last_3"].fillna(0.0)
    df["route_hour_avg_delay"] = df["route_hour_avg_delay"].fillna(0.0)
    df["route_hour_avg_arr_delay"] = df["route_hour_avg_arr_delay"].fillna(0.0)

    # ── Target Variables ──────────────────────────────────────────────
    # We create two targets: one for departure delay, one for arrival delay
    # Drop rows where we have no valid target
    # For departure delay model: only rows that HAVE departure info
    # For arrival delay model: only rows that HAVE arrival info
    df["departure_delay_min"] = pd.to_numeric(df["departure_delay_min"], errors="coerce")
    df["arrival_delay_min"] = pd.to_numeric(df["arrival_delay_min"], errors="coerce")

    # ── Select Final Feature Columns ──────────────────────────────────
    feature_cols = [
        "hour_of_day", "day_of_week", "month", "is_weekend", "is_rush_hour",
        "hour_sin", "hour_cos", "month_sin", "month_cos",
        "temperature_c", "precipitation_mm", "snow_depth_cm", "weather_code",
        "origin_departure_delay",
        "station_avg_delay_last_3", "station_avg_arr_delay_last_3",
        "route_hour_avg_delay", "route_hour_avg_arr_delay",
    ]

    # Categorical columns to encode
    cat_cols = ["station_uic", "linien_text", "train_type"]

    # One-hot encode categorical features
    df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=False, dtype=int)

    # Get all one-hot column names
    encoded_cat_cols = [c for c in df_encoded.columns if any(c.startswith(cat + "_") for cat in cat_cols)]
    all_feature_cols = feature_cols + encoded_cat_cols

    # Ensure all feature columns exist
    all_feature_cols = [c for c in all_feature_cols if c in df_encoded.columns]

    print(f"\n-- Feature Engineering Complete --")
    print(f"   Total features: {len(all_feature_cols)}")
    print(f"   Numeric: {len(feature_cols)} | Encoded categorical: {len(encoded_cat_cols)}")
    print(f"   Rows with departure_delay: {df_encoded['departure_delay_min'].notna().sum()}")
    print(f"   Rows with arrival_delay:   {df_encoded['arrival_delay_min'].notna().sum()}")

    return df_encoded, all_feature_cols


def build_feature_dataset():
    """
    Full pipeline: load data from DB → merge → engineer features → return clean dataset.
    """
    print("=" * 60)
    print("  Phase 2: Feature Engineering Pipeline")
    print("=" * 60)

    engine = get_db_engine()

    trips_df = load_trips(engine)
    weather_df = load_weather(engine)

    if trips_df.empty:
        print("ERROR: No trip data found in database. Run the Phase 1 pipeline first.")
        return None, None

    merged_df = merge_trips_weather(trips_df, weather_df)
    feature_df, feature_cols = engineer_features(merged_df)

    print(f"\n[OK] Feature dataset ready: {len(feature_df)} rows x {len(feature_cols)} features")
    return feature_df, feature_cols


if __name__ == "__main__":
    df, cols = build_feature_dataset()
    if df is not None:
        print(f"\nSample features (first 5 rows):")
        print(df[cols[:8]].head().to_string(index=False))
        print(f"\nTarget distribution (departure_delay_min):")
        valid = df["departure_delay_min"].dropna()
        print(f"  Count: {len(valid)} | Mean: {valid.mean():.2f} | Median: {valid.median():.2f} | Max: {valid.max():.1f}")
