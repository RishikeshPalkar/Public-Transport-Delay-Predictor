# Project Brief: SBB Public Transport Delay Predictor

This document provides a concise high-level overview of the SBB Delay Predictor platform.

---

## 💡 Why: The Purpose & Utility
Public transport punctuality is a core aspect of Swiss infrastructure and culture. This project solves key real-world challenges:
- **Commuter Empowerment**: Allows passengers to preview delay forecasts ahead of time, assisting in travel planning and preventing crowded station waits.
- **Connection Protection (*Taktfahrplan*)**: Pre-predicts arrival delays so dispatch systems can determine whether connecting trains should be held.
- **Weather Resilience**: Models the impact of weather conditions (like snow depth and heavy rainfall) on schedule stability, helping transit networks plan resources.

---

## ⚙️ What: The Features & Machine Learning
The platform predicts departure and arrival delays at **6 major Swiss railway hubs** (Zürich HB, Genève, Bern, Basel SBB, Lausanne, Lucerne).
- **Relational Data**: Persists historical and simulated schedule records and weather logs in a **MySQL** database.
- **Time-Series Features**: Engineers **32 variables** including cyclical time functions, rolling station delay trends, weather metrics, and train types.
- **XGBoost Regressors**: Separate models trained with chronological validation and early stopping to guarantee leakage-free, high-precision forecasts.
  - **Departure model accuracy**: R² of `0.9959` | MAE of `0.051 min`
  - **Arrival model accuracy**: R² of `0.9645` | MAE of `0.754 min`

---

## 🛠️ How: The Technical Architecture
The system is built as a microservices architecture:
- **Python FastAPI Service (Port 8000)**: Serves as the ML inference node. Loads serialized XGBoost models and evaluates prediction requests. Features database fallbacks to compute complex lags.
- **Java Spring Boot Gateway (Port 8081)**: Serves as the central backend orchestrator. Queries the MySQL database via Spring Data JPA, triggers FastAPI predictions using `RestTemplate`, and hosts the static UI.
- **Database (MySQL)**: Holds station, schedule, and weather observation tables.
- **Docker Compose**: Packages the database and FastAPI service into isolated, coordinate containers.

---

## 🖥️ What It Shows: The User Interface
When a user visits `http://localhost:8081/`, they interact with a modern **Glassmorphism Dark-Mode Dashboard**:
1. **Station Selector**: Allows selecting one of the 6 Swiss hubs, dynamically populated from the database.
2. **Local Weather Status**: Displays the current temperature, precipitation, and WMO weather icons.
3. **Interactive Timetable Board**:
   - **Departures Tab**: Displays the next 10 departures, showing scheduled time, line, destination, and the XGBoost predicted delay.
   - **Arrivals Tab**: Displays the next 10 arrivals, showing scheduled time, line, origin, and the XGBoost predicted delay.
4. **Color-Coded Forecast Badges**:
   - **Green (On Time)**: Delay $\le 0.2$ minutes.
   - **Orange (Warning)**: Delay between $0.2$ and $3.0$ minutes.
   - **Red (Delayed)**: Delay $\ge 3.0$ minutes.
