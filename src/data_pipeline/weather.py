import os
import json
import time
import requests
import pandas as pd
from datetime import datetime

# Directory for caching weather responses to avoid hitting rate limits
CACHE_DIR = os.path.join("data", "cache", "weather")

def fetch_historical_weather(uic_code, lat, lon, start_date, end_date):
    """
    Fetches historical hourly weather data for a specific coordinate and date range.
    Uses local filesystem caching to prevent duplicate external requests.
    
    Parameters:
    - uic_code: Station identifier (used for caching)
    - lat: Latitude of the station
    - lon: Longitude of the station
    - start_date: Start date string (YYYY-MM-DD)
    - end_date: End date string (YYYY-MM-DD)
    
    Returns:
    - List of dicts matching database schema fields for weather_observations.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{uic_code}_{start_date}_{end_date}.json")
    
    # 1. Check if cache exists
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                print(f"Loading cached weather data for station {uic_code}...")
                return json.load(f)
        except Exception as e:
            print(f"Error reading weather cache for {uic_code}: {e}. Fetching fresh data...")
            
    # 2. Query Open-Meteo Historical API
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,precipitation,snow_depth,weather_code",
        "timezone": "Europe/Zurich"
    }
    
    print(f"Fetching weather from Open-Meteo for station {uic_code} ({lat}, {lon}) from {start_date} to {end_date}...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {uic_code}: {e}")
            if attempt == max_retries - 1:
                print(f"Failed to fetch weather for {uic_code} after {max_retries} attempts.")
                return []
            time.sleep(2)
            
    # 3. Parse and convert response
    if "hourly" not in data:
        print(f"No hourly weather data found in response for station {uic_code}.")
        return []
        
    hourly = data["hourly"]
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    precips = hourly.get("precipitation", [])
    snows = hourly.get("snow_depth", [])
    codes = hourly.get("weather_code", [])
    
    records = []
    for i in range(len(times)):
        # Convert Open-Meteo time (YYYY-MM-DDTHH:MM) to datetime object
        # Example format: 2026-06-01T00:00
        raw_time = times[i]
        obs_time = datetime.strptime(raw_time, "%Y-%m-%dT%H:%M")
        
        # Open-Meteo returns snow depth in meters. Convert to cm.
        snow_depth_cm = float(snows[i] * 100.0) if snows[i] is not None else 0.0
        
        records.append({
            "station_uic": uic_code,
            "observation_time": obs_time.strftime("%Y-%m-%d %H:%M:%S"),
            "temperature_c": float(temps[i]) if temps[i] is not None else None,
            "precipitation_mm": float(precips[i]) if precips[i] is not None else 0.0,
            "snow_depth_cm": snow_depth_cm,
            "weather_code": int(codes[i]) if codes[i] is not None else None
        })
        
    # 4. Save to cache
    try:
        with open(cache_file, "w") as f:
            json.dump(records, f)
    except Exception as e:
        print(f"Failed to cache weather data for {uic_code}: {e}")
        
    # Standard rate limit breathing room for Open-Meteo (non-commercial tier)
    time.sleep(1)
    
    return records
