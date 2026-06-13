from fastapi import FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from typing import Dict, Any

from sqlalchemy import text
from src.api.schemas import PredictionRequest, PredictionResponse
from src.api.predictor import DelayPredictor

# Globals
predictor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events for the API application."""
    global predictor
    print("[API] Starting up: initializing model predictor...")
    try:
        predictor = DelayPredictor()
    except Exception as e:
        print(f"[API ERROR] Failed to initialize predictor: {e}")
    yield
    print("[API] Shutting down: cleaning up connections...")
    if predictor and predictor.db_engine:
        predictor.db_engine.dispose()

app = FastAPI(
    title="SBB Public Transport Delay Predictor API",
    description="Machine Learning REST API using XGBoost to predict train delays at major Swiss railway hubs.",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/", include_in_schema=False)
async def root():
    """Redirects visitors to the automated interactive API documentation (Swagger)."""
    return RedirectResponse(url="/docs")

@app.get("/health", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def health():
    """Checks the health of the API, database connectivity, and model loading status."""
    global predictor
    if not predictor:
        return {
            "status": "UNHEALTHY",
            "message": "Predictor engine not initialized"
        }
    
    # Check Database Connection
    db_ok = False
    try:
        with predictor.db_engine.connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()
            db_ok = True
    except Exception as e:
        db_message = str(e)
    
    # Check Model status
    models_loaded = predictor.dep_model is not None and predictor.arr_model is not None

    overall_status = "HEALTHY" if (db_ok and models_loaded) else "DEGRADED"
    
    return {
        "status": overall_status,
        "database_connected": db_ok,
        "models_loaded": {
            "departure_delay_xgb": predictor.dep_model is not None,
            "arrival_delay_xgb": predictor.arr_model is not None
        },
        "model_metadata": {
            "departure": predictor.dep_meta if predictor.dep_meta else "None",
            "arrival": predictor.arr_meta if predictor.arr_meta else "None"
        }
    }

@app.post("/predict/departure", response_model=PredictionResponse)
async def predict_departure(request: PredictionRequest):
    """
    Predicts the departure delay of a train in minutes.
    Automatically fetches lag/historical features from database if omitted.
    """
    global predictor
    if not predictor or not predictor.dep_model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Departure prediction model not loaded"
        )
    
    try:
        # Convert request Pydantic model to dictionary
        req_dict = request.model_dump()
        
        # Run prediction
        pred, features = predictor.predict_departure(req_dict)
        station_name = predictor.get_station_name(request.station_uic)
        
        # Train type
        import re
        train_type_match = re.match(r"([A-Z]+)", request.linien_text)
        train_type = train_type_match.group(1) if train_type_match else "OTHER"
        
        return PredictionResponse(
            predicted_delay_min=pred,
            station_uic=request.station_uic,
            station_name=station_name,
            train_type=train_type,
            scheduled_time=request.scheduled_time,
            features_used=features,
            model_metadata=predictor.dep_meta
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Departure prediction failed: {str(e)}"
        )

@app.post("/predict/arrival", response_model=PredictionResponse)
async def predict_arrival(request: PredictionRequest):
    """
    Predicts the arrival delay of a train in minutes.
    Automatically fetches lag/historical features from database if omitted.
    """
    global predictor
    if not predictor or not predictor.arr_model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Arrival prediction model not loaded"
        )
    
    try:
        # Convert request Pydantic model to dictionary
        req_dict = request.model_dump()
        
        # Run prediction
        pred, features = predictor.predict_arrival(req_dict)
        station_name = predictor.get_station_name(request.station_uic)
        
        # Train type
        import re
        train_type_match = re.match(r"([A-Z]+)", request.linien_text)
        train_type = train_type_match.group(1) if train_type_match else "OTHER"
        
        return PredictionResponse(
            predicted_delay_min=pred,
            station_uic=request.station_uic,
            station_name=station_name,
            train_type=train_type,
            scheduled_time=request.scheduled_time,
            features_used=features,
            model_metadata=predictor.arr_meta
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Arrival prediction failed: {str(e)}"
        )

@app.post("/reload", response_model=Dict[str, str])
async def reload_models():
    """Reloads the models and metadata from disk in-memory without restarting the server."""
    global predictor
    if not predictor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictor engine not initialized"
        )
    
    try:
        reload_results = predictor.reload_models()
        return reload_results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reload failed: {str(e)}"
        )
