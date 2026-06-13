import sys
import os
from datetime import datetime

# Insert project root into python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi.testclient import TestClient
from src.api.main import app

def test_api():
    print("Initializing TestClient with lifespan context...")
    with TestClient(app) as client:
        print("Testing /health endpoint...")
        response = client.get("/health")
        assert response.status_code == 200
        health_data = response.json()
        print("Health response status:", health_data.get("status"))
        print("Models loaded status:", health_data.get("models_loaded"))
        print("Database connected status:", health_data.get("database_connected"))
        
        # We will pick a station UIC and train line that exists (e.g. station UIC '8503000' representing Zürich HB)
        print("\nTesting /predict/departure endpoint...")
        payload = {
            "station_uic": "8503000",
            "linien_text": "IC8",
            "scheduled_time": "2026-06-14T08:30:00",
            "temperature_c": 18.5,
            "precipitation_mm": 0.0,
            "snow_depth_cm": 0.0,
            "weather_code": 0
        }
        response = client.post("/predict/departure", json=payload)
        print("Response status:", response.status_code)
        if response.status_code != 200:
            print("Error detail:", response.json())
        assert response.status_code == 200
        dep_data = response.json()
        print("Departure Prediction Result:", dep_data["predicted_delay_min"], "mins")
        print("Station Name queried:", dep_data["station_name"])
        print("Train Type:", dep_data["train_type"])
        
        # Let's test predict/arrival
        print("\nTesting /predict/arrival endpoint...")
        response = client.post("/predict/arrival", json=payload)
        print("Response status:", response.status_code)
        if response.status_code != 200:
            print("Error detail:", response.json())
        assert response.status_code == 200
        arr_data = response.json()
        print("Arrival Prediction Result:", arr_data["predicted_delay_min"], "mins")
        print("Station Name queried:", arr_data["station_name"])
    
    print("\n[SUCCESS] All API tests completed successfully!")

if __name__ == "__main__":
    try:
        test_api()
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        sys.exit(1)
