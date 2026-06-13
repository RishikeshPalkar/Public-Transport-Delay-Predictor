from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any

class PredictionRequest(BaseModel):
    station_uic: str = Field(..., description="UIC code of the station (e.g., '8500010')", example="8500010")
    linien_text: str = Field(..., description="Train line text (e.g., 'IC8', 'IR90', 'S12')", example="IC8")
    scheduled_time: datetime = Field(..., description="Scheduled time of arrival/departure in ISO format", example="2026-06-14T08:30:00")
    
    # Optional weather inputs (defaults to None, will use defaults or fallback if not provided)
    temperature_c: Optional[float] = Field(None, description="Temperature in Celsius. Defaults to 15.0 if missing.", example=12.5)
    precipitation_mm: Optional[float] = Field(None, description="Precipitation in mm. Defaults to 0.0 if missing.", example=0.0)
    snow_depth_cm: Optional[float] = Field(None, description="Snow depth in cm. Defaults to 0.0 if missing.", example=0.0)
    weather_code: Optional[int] = Field(None, description="WMO Weather code. Defaults to 0 (Clear) if missing.", example=0)
    
    # Optional cross-trip and lag features (if omitted, API will look up in database or default to 0.0)
    origin_departure_delay: Optional[float] = Field(None, description="Departure delay of this train at its origin station. Defaults to 0.0.", example=2.0)
    station_avg_delay_last_3: Optional[float] = Field(None, description="Average departure delay of the last 3 trains at this station. Auto-queried from DB if missing.", example=1.5)
    station_avg_arr_delay_last_3: Optional[float] = Field(None, description="Average arrival delay of the last 3 trains at this station. Auto-queried from DB if missing.", example=0.8)
    route_hour_avg_delay: Optional[float] = Field(None, description="Historical average departure delay for this route and hour. Auto-queried from DB if missing.", example=1.2)
    route_hour_avg_arr_delay: Optional[float] = Field(None, description="Historical average arrival delay for this route and hour. Auto-queried from DB if missing.", example=1.0)


class PredictionResponse(BaseModel):
    predicted_delay_min: float = Field(..., description="Predicted delay in minutes (non-negative)", example=1.45)
    station_uic: str = Field(..., description="Target station UIC", example="8500010")
    station_name: Optional[str] = Field(None, description="Name of the station", example="Zürich HB")
    train_type: str = Field(..., description="Extracted train type (e.g. IC, IR, S)", example="IC")
    scheduled_time: datetime = Field(..., description="Target scheduled time", example="2026-06-14T08:30:00")
    features_used: Dict[str, Any] = Field(..., description="The exact feature variables passed to the model (including DB lookups)")
    model_metadata: Dict[str, Any] = Field(..., description="Model version, metrics, and training configuration details")
