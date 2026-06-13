# Public Transport Delay Predictor – Phase 1: Data Ingestion & Pipeline

A high-performance, portfolio-grade public transport delay prediction pipeline designed for Swiss railway (SBB) network analytics. The architecture is specifically optimized for a solo developer workflow, prioritizing low storage footprint (<20 MB) and high CPU efficiency while preserving rich historical patterns suitable for machine learning research (targeting EPFL/ETHZ style projects).

---

## 🎯 Phase 1 Goals & Strategy

The primary goal of Phase 1 is to establish a robust, reliable data pipeline that fetches or simulates historical railway trips and hourly weather observations, structure them into a relational database, and support incremental daily updates.

### 💡 Solo-Developer & Portfolio Optimization Strategy
1. **Station Filtering**: Focuses on **6 major Swiss railway hubs** representing distinct geographical cantons. This reduces the raw SBB dataset size (which can be gigabytes) to a highly compact database of **~10–20 MB** without losing structural complexity.
2. **6-Month Historical Training Window**: Ingests/simulates a continuous **6-month historical window** (e.g., `2026-01-01` to `2026-06-30`). This generates 65,000+ trip records and 26,000+ weather records—providing sufficient seasonal, daily, and meteorological variance for XGBoost training.
3. **Daily Incremental Ingestion**: After the initial historical load, the pipeline shifts to **daily ingestion** (yesterday-to-yesterday). It performs target-range deletions and appends new records, ensuring no duplicate entries while keeping the historical training data fully intact.

---

## 🗂️ Project Structure

```
Public Transport Delay Predictor/
│   .env                 # Environment configurations (credentials, dates, modes)
│   .env.example         # Template for environment configuration
│   requirements.txt     # Python dependency definition
│   README.md            # ← Project documentation (this file)
│   run_pipeline.bat     # Windows automated pipeline launcher
│
├── src/
│   ├── data_pipeline/
│   │    ├─ ingest.py    # Pipeline orchestrator (DB setup, seeding, flow control)
│   │    ├─ weather.py   # Historical weather retrieval via Open-Meteo API
│   │    ├─ downloader.py# Automated downloader for SBB Actual Data archives
│   │    ├─ cleaner.py   # Normalizes, filters, and validates SBB raw data
│   │    └─ simulator.py # High-performance SBB trip and weather synthesizer
│   │
│   ├── ml/
│   │    ├─ features.py  # DB feature extraction and cyclical time engineering
│   │    └─ train.py     # XGBoost Model training with early stopping & evaluation
│   │
│   └── api/
│        ├─ schemas.py   # Pydantic request and response definitions
│        ├─ predictor.py # Model scoring engine with database-driven lag fallbacks
│        ├─ main.py      # FastAPI application hosting ML routes
│        └─ test_api.py  # Automated endpoint verification suite
│
├── database/
│    └─ schema.sql       # Reference SQL Schema (mirrored by SQLAlchemy MetaData)
│
└── models/              # Persisted model binaries and metadata configurations
```

---

## 📊 Relational Database Schema

The relational schema is configured to support database-agnostic operations (MySQL local instance with SQLite fallback) using **SQLAlchemy 2.0**.

### 1. `stations`
Stores metadata for the tracked Swiss transport hubs.
- `uic_code` (PK): Unique Swiss/European station identifier.
- `name`, `latitude`, `longitude`, `canton`.

### 2. `weather_observations`
Hourly weather records for each station.
- `id` (PK), `station_uic` (FK), `observation_time` (Datetime).
- `temperature_c` (Celsius), `precipitation_mm` (Rainfall), `snow_depth_cm`, `weather_code` (WMO weather code).
- *Constraint*: `uq_station_time` (Unique index on `station_uic` + `observation_time` to prevent duplicate hours).

### 3. `trips`
Train arrival/departure records.
- `id` (PK), `betriebstag` (Date of operation), `fahrt_bezeichner` (Unique SBB journey identifier), `produkt_id` (e.g., Zug), `linien_text` (e.g., IC8, IR90, S12).
- `station_uic` (FK), `station_name`.
- `scheduled_arrival`, `actual_arrival`, `arrival_delay_min`.
- `scheduled_departure`, `actual_departure`, `departure_delay_min`.
- `faellt_aus` (Boolean, cancellation), `zusatzfahrt` (Boolean, additional service).
- *Constraint*: `uq_trip_stop` (Unique index on `betriebstag` + `fahrt_bezeichner` + `station_uic`).

---

## ⚙️ Setup & Configuration

### 1. Install Dependencies
Ensure you are using Python 3.11+. Create a virtual environment and install dependencies:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Variables (`.env`)
Configure your `.env` file by copying the template:
```powershell
copy .env.example .env
```
Update the credentials and target dates inside `.env`:
- **For the 6-Month Historical Load**:
  ```ini
  DB_TYPE=mysql
  DB_USER=root
  DB_PASSWORD=your_password
  DB_NAME=sbb_delays
  SIMULATION_MODE=True
  START_DATE=2026-01-01
  END_DATE=2026-06-30
  ```
- **For Daily Incremental Ingestion**:
  Once the historical data is populated, switch the dates to:
  ```ini
  START_DATE=yesterday
  END_DATE=yesterday
  ```

---

## ▶️ Running the Pipeline

To execute the data ingestion pipeline:
```powershell
python src/data_pipeline/ingest.py
```
Alternatively, double-click the Windows automation shortcut:
```powershell
.\run_pipeline.bat
```

### Execution Flow:
1. **Connection & DB Setup**: Verifies MySQL server, creates `sbb_delays` database if missing, and initializes tables.
2. **Metadata Seeding**: Inserts the 6 target Swiss stations into the `stations` table.
3. **Target Ingestion**:
   - Deletes existing records in the target range (`START_DATE` to `END_DATE`) to allow clean reruns.
   - Generates/Ingests hourly weather records and inserts them.
   - Generates/Ingests trip-stop delay records and inserts them.
4. **Summary Printout**: Reports final counts of stations, weather observations, and trips currently stored in the database.

---

## 🧪 Verification & Validation Output

A successful 6-month historical run logs the following in the console:
```text
Ensured MySQL database 'sbb_delays' exists.
Connecting to database via URL: mysql+mysqlconnector://root:***@localhost:3306/sbb_delays
Initializing Database Schema...
Seeding station metadata...
Executing ingestion pipeline for range: 2026-01-01 to 2026-06-30

--- Running Pipeline in SIMULATION MODE (2026-01-01 to 2026-06-30) ---
Generating simulated weather observations...
Inserted 26064 simulated weather observation records.
Generating simulated SBB trips...
Inserted 65160 simulated trip stop records.

Inference pipeline database overview:
- Stations stored: 6
- Weather observations: 26064
- Trip records stored: 65160

Phase 1 Data Pipeline execution successfully completed!
```

---

## 🚀 Phase 2: Feature Engineering & ML

Using the ingested 6-month training data, the pipeline builds 32 features and trains high-performance models.

### 1. Feature Engineering (`src/ml/features.py`)
- **Temporal**: Hour of day, day of week, month, weekend status, rush hour flag, and sine/cosine cyclical transformations.
- **Cross-Trip**: Propagates departure delay from the train's origin to target arrival records (`origin_departure_delay`), eliminating model underperformance.
- **Station Lags**: Calculates rolling average delay of the last 3 trains at each hub (shifted by 1 to prevent leakage).
- **Historical Averages**: Computes historical averages grouped by train line and hour of day.

### 2. Model Training (`src/ml/train.py`)
- Trains separate `XGBRegressor` models for departure and arrival delay predictions.
- Splits dataset chronologically (Jan-May train, June test) to mirror real-world forecasting.
- Applies **early stopping** (`early_stopping_rounds=20`) to prevent overfitting.
- **Performance**:
  - **Departure Model**: MAE: `0.051 min` | RMSE: `0.324 min` | R²: `0.9959`
  - **Arrival Model**: MAE: `0.754 min` | RMSE: `0.968 min` | R²: `0.9645`

---

## ⚡ Phase 3: Prediction REST API (`src/api/`)

A production-grade REST API built using **FastAPI** to serve delay forecasts programmatically.

### Key Features
1. **Auto Feature Generation**: The client only sends basic details (`station_uic`, `linien_text`, `scheduled_time`, and optionally weather). The API automatically calculates cyclical features and one-hot values.
2. **Database Fallbacks**: If lag or historical delay variables are missing in the request, the API queries the database dynamically to compute them.
3. **Hot reloading**: Supports the `/reload` endpoint to reload model files in-memory without server restarts.

### Running the API
Start the local server using Uvicorn:
```powershell
.venv\Scripts\python -m uvicorn src.api.main:app --reload
```
Navigate to `http://127.0.0.1:8000/docs` in your browser to access the interactive Swagger UI.

### Running Verification Tests
Execute the automated `TestClient` suite:
```powershell
.venv\Scripts\python src/api/test_api.py
```

---

## 🐳 Phase 4: Docker Containerization

We containerized the entire solution using **Docker** and **Docker Compose** to run both MySQL and the FastAPI server seamlessly in isolated environments.

### Services Defined
1. **`db` (MySQL 8.0)**: Relational database to persist station records, trip logs, and weather observations.
2. **`api` (FastAPI backend)**: Runs an orchestration entrypoint that:
   - Waits for MySQL to be fully online and healthy.
   - Runs database setup and data ingestion (`ingest.py`).
   - Automatically trains models if missing from the `models/` directory (`train.py`).
   - Launches the FastAPI Uvicorn web server.

### Running with Docker Compose
Ensure Docker Desktop is started and running on your system, then execute:
```powershell
docker compose up --build
```
The server will be exposed on port `8000`. You can query the endpoints or open `http://localhost:8000/docs`.

