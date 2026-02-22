from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class LocationInfo(BaseModel):
    lat: float
    lon: float
    radius_m: int
    address: str
    timestamp: datetime


class VehicleProfile(BaseModel):
    vehicle_type: str = Field(..., description="passenger | truck | taxi | fhv")
    commercial_plate: bool


class ParkingRule(BaseModel):
    type: str
    description: str
    fine: Optional[int] = None
    next_cleaning: Optional[datetime] = None
    window: Optional[str] = None
    time_left: Optional[str] = None
    rate: Optional[str] = None
    max_time: Optional[str] = None
    hours: Optional[str] = None
    active_now: Optional[bool] = None
    severity: Optional[str] = None
    valid: bool
    reason: Optional[str] = None
    source: str


class SourceInfo(BaseModel):
    regulations: str
    meters: str


class ParkingDecision(BaseModel):
    status: str = Field(..., description="safe | caution | blocked")
    risk_score: int = Field(..., ge=0, le=100)
    primary_reason: str
    recommended_action: str


class ParkingStatusResponse(BaseModel):
    location: LocationInfo
    vehicle_profile: VehicleProfile
    rules: list[ParkingRule]
    parking_decision: ParkingDecision
    confidence: float = Field(..., ge=0.0, le=1.0)
    warning: Optional[str] = None
    sources: SourceInfo
    next_cleaning: Optional[datetime] = None
