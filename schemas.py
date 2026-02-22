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
    valid: bool
    reason: Optional[str] = None
    source: str


class SourceInfo(BaseModel):
    regulations: str
    meters: str


class ParkingStatusResponse(BaseModel):
    location: LocationInfo
    rules: list[ParkingRule]
    confidence: float = Field(..., ge=0.0, le=1.0)
    warning: Optional[str] = None
    sources: SourceInfo
    next_cleaning: Optional[datetime] = None
