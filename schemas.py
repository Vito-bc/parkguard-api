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
    agency_affiliation: str = Field(..., description="none | police | fire | city | school")


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
    distance_ft: Optional[float] = None
    threshold_ft: Optional[float] = None
    eligible_vehicle_types: Optional[list[str]] = None
    active_now: Optional[bool] = None
    severity: Optional[str] = None
    valid: bool
    reason: Optional[str] = None
    source: str
    violation_estimate: Optional["ViolationEstimate"] = None


class SourceInfo(BaseModel):
    regulations: str
    meters: str


class FreshnessInfo(BaseModel):
    status: str
    cache_hit: Optional[bool] = None
    fetched_at: Optional[datetime] = None


class DataFreshness(BaseModel):
    regulations: FreshnessInfo
    meters: FreshnessInfo
    hydrants: FreshnessInfo


class ParkingDecision(BaseModel):
    status: str = Field(..., description="safe | caution | blocked")
    risk_score: int = Field(..., ge=0, le=100)
    primary_reason: str
    recommended_action: str


class ViolationEstimate(BaseModel):
    violation_code: Optional[str] = None
    min_fine_usd: int
    max_fine_usd: int
    jurisdiction: str = "NYC"
    confidence: float = Field(..., ge=0.0, le=1.0)
    note: Optional[str] = None
    fine_source: Optional[str] = None
    last_updated: Optional[str] = None


class ViolationSummary(BaseModel):
    estimated_total_min_usd: int
    estimated_total_max_usd: int
    highest_single_max_usd: int
    high_risk_violations: int
    currency: str = "USD"


class ParkingStatusResponse(BaseModel):
    location: LocationInfo
    vehicle_profile: VehicleProfile
    rules: list[ParkingRule]
    parking_decision: ParkingDecision
    violation_summary: ViolationSummary
    data_freshness: DataFreshness
    confidence: float = Field(..., ge=0.0, le=1.0)
    warning: Optional[str] = None
    sources: SourceInfo
    next_cleaning: Optional[datetime] = None
