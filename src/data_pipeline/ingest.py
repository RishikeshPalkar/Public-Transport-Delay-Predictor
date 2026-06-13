import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, UniqueConstraint, select, func
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import insert  # We will use general upsert/insert

# Import pipeline modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from weather import fetch_historical_weather
from downloader import download_sbb_actual_data
from cleaner import clean_sbb_chunk
from simulator import SWISS_STATIONS, generate_weather_for_range, generate_trips_for_range

# Define Schema via SQLAlchemy MetaData for cross-database compatibility
metadata = MetaData()

stations_table = Table(
    'stations', metadata,
    Column('uic_code', String(20), primary_key=True),
    Column('name', String(100), nullable=False, unique=True),
    Column('latitude', Float),
    Column('longitude', Float),
    Column('canton', String(10))
)

weather_table = Table(
    'weather_observations', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('station_uic', String(20), ForeignKey('stations.uic_code', ondelete='CASCADE'), nullable=False),
    Column('observation_time', DateTime, nullable=False),
    Column('temperature_c', Float),
    Column('precipitation_mm', Float),
    Column('snow_depth_cm', Float),
    Column('weather_code', Integer),
    UniqueConstraint('station_uic', 'observation_time', name='uq_station_time')
)

trips_table = Table(
    'trips', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('betriebstag', Date, nullable=False),
    Column('fahrt_bezeichner', String(100), nullable=False),
    Column('produkt_id', String(20)),
    Column('linien_text', String(50)),
    Column('station_uic', String(20), ForeignKey('stations.uic_code', ondelete='CASCADE'), nullable=False),
    Column('station_name', String(100), nullable=False),
    Column('scheduled_arrival', DateTime),
    Column('actual_arrival', DateTime),
    Column('arrival_delay_min', Float),
    Column('scheduled_departure', DateTime),
    Column('actual_departure', DateTime),
    Column('departure_delay_min', Float),
    Column('faellt_aus', Boolean, default=False),
    Column('zusatzfahrt', Boolean, default=False),
    UniqueConstraint('betriebstag', 'fahrt_bezeichner', 'station_uic', name='uq_trip_stop')
)

def get_db_engine():
    """
    Creates and returns a database engine based on .env config.
    """
    load_dotenv()
    db_type = os.getenv("DB_TYPE", "sqlite").lower()
    
    if db_type == "mysql":
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "3306")
        name = os.getenv("DB_NAME", "sbb_delays")
        
        # We will attempt to connect to MySQL. 
        # If the database does not exist, we try to create it first.
        try:
            temp_engine = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/")
            with temp_engine.connect() as conn:
                conn.execute(f"CREATE DATABASE IF NOT EXISTS {name}")
                print(f"Ensured MySQL database '{name}' exists.")
        except Exception as e:
            print(f"Could not initialize MySQL database '{name}': {e}.")
            print("Falling back to SQLite database...")
            db_type = "sqlite"

    if db_type == "sqlite":
        sqlite_path = os.getenv("SQLITE_PATH", "data/sbb_delays.db")
        os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
        db_url = f"sqlite:///{sqlite_path}"
    else:
        db_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{name}"
        
    print(f"Connecting to database via URL: {db_url}")
    return create_engine(db_url)

def seed_stations(engine):
    """
    Seeds the stations metadata table.
    """
    with engine.begin() as conn:
        for station in SWISS_STATIONS:
            # Query if station exists
            query = select(stations_table).where(stations_table.c.uic_code == station["uic_code"])
            result = conn.execute(query).fetchone()
            if not result:
                conn.execute(stations_table.insert().values(
                    uic_code=station["uic_code"],
                    name=station["name"],
                    latitude=station["latitude"],
                    longitude=station["longitude"],
                    canton=station["canton"]
                ))
                print(f"Seeded station: {station['name']} ({station['uic_code']})")

def run_simulation(engine, start_date, end_date):
    """
    Runs pipeline in simulation mode, generating synthetic trip and weather records.
    """
    print(f"\n--- Running Pipeline in SIMULATION MODE ({start_date} to {end_date}) ---")
    
    # 1. Generate Weather
    print("Generating simulated weather observations...")
    weather_df = generate_weather_for_range(start_date, end_date)
    
    # Write to database (overwrite/append)
    with engine.begin() as conn:
        # Convert observation time column to datetime object for correct DB insertion
        weather_df["observation_time"] = pd.to_datetime(weather_df["observation_time"])
        
        # Clean older records to avoid constraint violations
        conn.execute(weather_table.delete())
        weather_df.to_sql('weather_observations', con=conn, if_exists='append', index=False)
        print(f"Inserted {len(weather_df)} simulated weather observation records.")
        
    # 2. Generate Trips
    print("Generating simulated SBB trips...")
    trips_df = generate_trips_for_range(start_date, end_date, weather_df)
    
    with engine.begin() as conn:
        trips_df["betriebstag"] = pd.to_datetime(trips_df["betriebstag"]).dt.date
        trips_df["scheduled_arrival"] = pd.to_datetime(trips_df["scheduled_arrival"])
        trips_df["actual_arrival"] = pd.to_datetime(trips_df["actual_arrival"])
        trips_df["scheduled_departure"] = pd.to_datetime(trips_df["scheduled_departure"])
        trips_df["actual_departure"] = pd.to_datetime(trips_df["actual_departure"])
        
        # Clean older records
        conn.execute(trips_table.delete())
        trips_df.to_sql('trips', con=conn, if_exists='append', index=False)
        print(f"Inserted {len(trips_df)} simulated trip stop records.")

def run_real_ingestion(engine, start_date, end_date):
    """
    Runs pipeline in REAL mode: downloads daily actual data, cleans it, and fetches weather.
    """
    print(f"\n--- Running Pipeline in REAL MODE ({start_date} to {end_date}) ---")
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    # 1. Fetch historical weather observations for target dates
    print("Fetching weather conditions from Open-Meteo...")
    weather_records = []
    for station in SWISS_STATIONS:
        records = fetch_historical_weather(
            uic_code=station["uic_code"],
            lat=station["latitude"],
            lon=station["longitude"],
            start_date=start_date,
            end_date=end_date
        )
        weather_records.extend(records)
        
    if weather_records:
        weather_df = pd.DataFrame(weather_records)
        weather_df["observation_time"] = pd.to_datetime(weather_df["observation_time"])
        with engine.begin() as conn:
            # Drop old weather for date range and insert new
            conn.execute(weather_table.delete().where(
                weather_table.c.observation_time.between(start_dt, end_dt)
            ))
            weather_df.to_sql('weather_observations', con=conn, if_exists='append', index=False)
            print(f"Ingested {len(weather_df)} weather records.")
            
    # 2. Download and process SBB actual data (daily/monthly files)
    # SBB archives are grouped by month, so find unique months in the range
    current_dt = start_dt
    months_to_process = set()
    while current_dt <= end_dt:
        months_to_process.add((current_dt.year, current_dt.month))
        current_dt += timedelta(days=28)  # Advance roughly a month
    months_to_process.add((end_dt.year, end_dt.month))
    
    for year, month in sorted(months_to_process):
        success = download_sbb_actual_data(year, month)
        if not success:
            print(f"Skipping processing for {year}-{month:02d} due to download failure.")
            continue
            
        # Scan raw/year-month folder for CSVs
        extracted_dir = os.path.join("data", "raw", f"{year}-{month:02d}")
        if not os.path.exists(extracted_dir):
            continue
            
        csv_files = [os.path.join(extracted_dir, f) for f in os.listdir(extracted_dir) if f.endswith('.csv')]
        
        for csv_file in sorted(csv_files):
            # Extract date from filename if possible, to filter by ingestion range
            # Format typically: YYYY-MM-DD_istdaten.csv
            basename = os.path.basename(csv_file)
            try:
                file_date_str = basename.split('_')[0].split('-')
                file_date = datetime(int(file_date_str[0]), int(file_date_str[1]), int(file_date_str[2]))
                if not (start_dt <= file_date <= end_dt):
                    continue  # Skip files outside requested range
            except Exception:
                pass
                
            print(f"Processing SBB file: {basename}...")
            
            # Read in chunks to keep memory usage low (SBB files are large)
            chunk_size = 50000
            total_inserted = 0
            
            try:
                # SBB files use semicolon separators
                for chunk in pd.read_csv(csv_file, sep=';', chunksize=chunk_size, low_memory=False):
                    cleaned_df = clean_sbb_chunk(chunk, SWISS_STATIONS)
                    if not cleaned_df.empty:
                        cleaned_df["betriebstag"] = pd.to_datetime(cleaned_df["betriebstag"]).dt.date
                        cleaned_df["scheduled_arrival"] = pd.to_datetime(cleaned_df["scheduled_arrival"])
                        cleaned_df["actual_arrival"] = pd.to_datetime(cleaned_df["actual_arrival"])
                        cleaned_df["scheduled_departure"] = pd.to_datetime(cleaned_df["scheduled_departure"])
                        cleaned_df["actual_departure"] = pd.to_datetime(cleaned_df["actual_departure"])
                        
                        with engine.begin() as conn:
                            # Load cleaned trips into SQLite/MySQL
                            cleaned_df.to_sql('trips', con=conn, if_exists='append', index=False)
                            total_inserted += len(cleaned_df)
                            
                print(f"Finished processing {basename}. Ingested {total_inserted} trip leg records.")
            except Exception as e:
                print(f"Error processing {csv_file}: {e}")

def main():
    load_dotenv()
    engine = get_db_engine()
    
    print("Initializing Database Schema...")
    metadata.create_all(engine)
    
    print("Seeding station metadata...")
    seed_stations(engine)
    
    simulation_mode = os.getenv("SIMULATION_MODE", "True").lower() == "true"
    start_date = os.getenv("START_DATE", "2026-06-01")
    end_date = os.getenv("END_DATE", "2026-06-07")
    
    if simulation_mode:
        run_simulation(engine, start_date, end_date)
    else:
        run_real_ingestion(engine, start_date, end_date)
        
    print("\nInference pipeline database overview:")
    with engine.connect() as conn:
        stations_count = conn.execute(select(func.count()).select_from(stations_table)).scalar()
        weather_count = conn.execute(select(func.count()).select_from(weather_table)).scalar()
        trips_count = conn.execute(select(func.count()).select_from(trips_table)).scalar()
        
        print(f"- Stations stored: {stations_count}")
        print(f"- Weather observations: {weather_count}")
        print(f"- Trip records stored: {trips_count}")
    print("\nPhase 1 Data Pipeline execution successfully completed!")

if __name__ == "__main__":
    main()
