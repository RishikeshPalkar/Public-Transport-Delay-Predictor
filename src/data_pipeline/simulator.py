import random
import math
from datetime import datetime, timedelta
import pandas as pd

# List of major Swiss hubs with coordinates and Cantons
SWISS_STATIONS = [
    {"uic_code": "8503000", "name": "Zürich HB", "latitude": 47.378177, "longitude": 8.540192, "canton": "ZH"},
    {"uic_code": "8507000", "name": "Bern", "latitude": 46.948825, "longitude": 7.439130, "canton": "BE"},
    {"uic_code": "8501000", "name": "Genève", "latitude": 46.210206, "longitude": 6.142456, "canton": "GE"},
    {"uic_code": "8506000", "name": "Winterthur", "latitude": 47.500244, "longitude": 8.724326, "canton": "ZH"},
    {"uic_code": "8500010", "name": "Basel SBB", "latitude": 47.547407, "longitude": 7.589548, "canton": "BS"},
    {"uic_code": "8501120", "name": "Lausanne", "latitude": 46.516777, "longitude": 6.629094, "canton": "VD"},
]

# Popular routes: (Origin, Destination, LinienText, TravelTimeMinutes)
ROUTES = [
    ("Zürich HB", "Bern", "IC8", 56),
    ("Bern", "Zürich HB", "IC8", 56),
    ("Zürich HB", "Winterthur", "IR75", 22),
    ("Winterthur", "Zürich HB", "IR75", 22),
    ("Genève", "Lausanne", "IR90", 36),
    ("Lausanne", "Genève", "IR90", 36),
    ("Basel SBB", "Zürich HB", "IC3", 53),
    ("Zürich HB", "Basel SBB", "IC3", 53),
    ("Zürich HB", "Winterthur", "S12", 28),
    ("Winterthur", "Zürich HB", "S12", 28),
]

def generate_weather_for_range(start_date, end_date):
    """
    Generates realistic hourly weather data for each station in SWISS_STATIONS.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days + 1
    
    weather_records = []
    
    for station in SWISS_STATIONS:
        # Base temperature varies slightly by latitude/elevation
        base_temp = 12.0 if station["canton"] != "BE" else 10.0 # Bern is slightly cooler
        
        for day in range(days):
            current_day = start + timedelta(days=day)
            
            # Determine overall weather condition for this day
            day_type = random.choices(["sunny", "cloudy", "rainy", "snowy"], weights=[0.4, 0.3, 0.2, 0.1])[0]
            
            for hour in range(24):
                obs_time = current_day.replace(hour=hour, minute=0, second=0)
                
                # Temperature curve: coldest at 5am, warmest at 3pm
                diurnal_effect = -5.0 * math.cos((hour - 5) * 2 * math.pi / 24)
                temp = base_temp + diurnal_effect + random.normalvariate(0, 1.5)
                
                # Snow vs Rain based on temperature
                precipitation = 0.0
                snow_depth = 0.0
                weather_code = 0  # Clear sky
                
                if day_type == "rainy":
                    precipitation = max(0.0, random.normalvariate(0.8, 1.2))
                    weather_code = 61 if precipitation < 2 else 63 # Rain: slight or moderate
                    temp -= 2.0  # Rain cools the air
                elif day_type == "snowy":
                    temp = min(temp - 8.0, 1.0)  # Make sure it's cold enough
                    precipitation = max(0.0, random.normalvariate(0.5, 0.8))
                    snow_depth = max(0.0, precipitation * 10)  # 1mm precip = 1cm snow depth
                    weather_code = 71 if precipitation < 1 else 73 # Snow: slight or moderate
                elif day_type == "cloudy":
                    weather_code = 3  # Overcast
                
                weather_records.append({
                    "station_uic": station["uic_code"],
                    "observation_time": obs_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "temperature_c": round(temp, 1),
                    "precipitation_mm": round(precipitation, 2),
                    "snow_depth_cm": round(snow_depth, 1),
                    "weather_code": weather_code
                })
                
    return pd.DataFrame(weather_records)

def generate_trips_for_range(start_date, end_date, weather_df):
    """
    Generates realistic SBB train trips with delays correlated with weather,
    station density, hour of the day, and day of the week.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days + 1
    
    trip_records = []
    
    # Pre-parse weather timestamps and build a fast lookup dictionary (O(1) lookups)
    # Key: (station_uic, date_object, hour) -> (precipitation_mm, snow_depth_cm)
    weather_lookup = {}
    weather_df_copy = weather_df.copy()
    weather_df_copy["parsed_time"] = pd.to_datetime(weather_df_copy["observation_time"])
    for _, row in weather_df_copy.iterrows():
        dt = row["parsed_time"]
        key = (str(row["station_uic"]), dt.date(), dt.hour)
        weather_lookup[key] = {
            "precipitation_mm": float(row["precipitation_mm"]),
            "snow_depth_cm": float(row["snow_depth_cm"])
        }
    
    # Station mappings for quick lookup
    station_lookup = {s["name"]: s for s in SWISS_STATIONS}
    
    for day in range(days):
        current_date = start + timedelta(days=day)
        date_str = current_date.strftime("%Y-%m-%d")
        day_of_week = current_date.weekday() # 0 = Monday, 6 = Sunday
        
        # SBB runs frequent trains: we run hourly schedules on each route between 06:00 and 23:00
        for route in ROUTES:
            origin_name, dest_name, line, travel_time = route
            origin = station_lookup[origin_name]
            dest = station_lookup[dest_name]
            
            for hour in range(6, 24):
                # Unique journey ID (incorporating origin and destination to prevent collisions on bidirectional routes)
                journey_num = 1000 + hour * 10 + random.randint(1, 9)
                journey_id = f"85:11:{line}_{origin['uic_code']}_{dest['uic_code']}_{journey_num}"
                
                # Scheduled departure from origin
                scheduled_dep_orig = current_date.replace(hour=hour, minute=0, second=0)
                
                # Scheduled arrival at destination
                scheduled_arr_dest = scheduled_dep_orig + timedelta(minutes=travel_time)
                
                # Get weather at origin to influence delays
                orig_key = (origin["uic_code"], current_date.date(), hour)
                origin_weather = weather_lookup.get(orig_key, {"precipitation_mm": 0.0, "snow_depth_cm": 0.0})
                
                rain = origin_weather["precipitation_mm"]
                snow = origin_weather["snow_depth_cm"]

                
                # Calculate factors influencing delay
                # 1. Rush hour factor (07:00-09:00, 16:30-18:30)
                rush_hour = 1.8 if (7 <= hour <= 9 or 16 <= hour <= 18) else 1.0
                
                # 2. Weekend/Friday factor
                day_factor = 1.3 if day_of_week == 4 else (0.8 if day_of_week in [5, 6] else 1.0)
                
                # 3. Weather factor (rain increases delay, snow significantly increases delay)
                weather_factor = 1.0 + (rain * 0.5) + (snow * 1.2)
                
                # 4. Route factor
                route_factor = 1.2 if "IC" in line else 1.0 # ICs cover longer distances, higher chance of upstream delay
                
                # Combine factors into a scale for exponential distribution
                delay_scale = 1.2 * rush_hour * day_factor * weather_factor * route_factor
                
                # Generate actual delay (exponential distribution: mostly small, sometimes large)
                # 80% chance of standard delay, 5% chance of high delay, 15% completely on-time (0 delay)
                rand_val = random.random()
                if rand_val < 0.15:
                    orig_dep_delay = 0.0
                else:
                    orig_dep_delay = round(random.expovariate(1.0 / delay_scale), 1)
                    # Limit extreme simulated delays to 45 mins
                    orig_dep_delay = min(orig_dep_delay, 45.0)
                
                # Actual departure from origin
                actual_dep_orig = scheduled_dep_orig + timedelta(minutes=orig_dep_delay)
                
                # Destination arrival delay propagates from departure delay with some random transit adjustment
                transit_variance = random.normalvariate(0.5, 1.0) # Trains might make up 30 secs or lose a minute
                dest_arr_delay = max(0.0, round(orig_dep_delay + transit_variance, 1))
                actual_arr_dest = scheduled_arr_dest + timedelta(minutes=dest_arr_delay)
                
                # Cancelled trains (faellt_aus) -> 0.5% chance
                faellt_aus = random.random() < 0.005
                
                # Extra trains (zusatzfahrt) -> 1% chance
                zusatzfahrt = random.random() < 0.01
                
                if faellt_aus:
                    actual_dep_orig = None
                    actual_arr_dest = None
                    orig_dep_delay = None
                    dest_arr_delay = None
                
                # Create origin trip row
                trip_records.append({
                    "betriebstag": date_str,
                    "fahrt_bezeichner": journey_id,
                    "produkt_id": "Zug",
                    "linien_text": line,
                    "station_uic": origin["uic_code"],
                    "station_name": origin["name"],
                    "scheduled_arrival": None, # Origin has no arrival
                    "actual_arrival": None,
                    "arrival_delay_min": None,
                    "scheduled_departure": scheduled_dep_orig.strftime("%Y-%m-%d %H:%M:%S"),
                    "actual_departure": actual_dep_orig.strftime("%Y-%m-%d %H:%M:%S") if actual_dep_orig else None,
                    "departure_delay_min": orig_dep_delay,
                    "faellt_aus": faellt_aus,
                    "zusatzfahrt": zusatzfahrt
                })
                
                # Create destination trip row
                trip_records.append({
                    "betriebstag": date_str,
                    "fahrt_bezeichner": journey_id,
                    "produkt_id": "Zug",
                    "linien_text": line,
                    "station_uic": dest["uic_code"],
                    "station_name": dest["name"],
                    "scheduled_arrival": scheduled_arr_dest.strftime("%Y-%m-%d %H:%M:%S"),
                    "actual_arrival": actual_arr_dest.strftime("%Y-%m-%d %H:%M:%S") if actual_arr_dest else None,
                    "arrival_delay_min": dest_arr_delay,
                    "scheduled_departure": None, # Destination has no departure
                    "actual_departure": None,
                    "departure_delay_min": None,
                    "faellt_aus": faellt_aus,
                    "zusatzfahrt": zusatzfahrt
                })
                
    return pd.DataFrame(trip_records)
