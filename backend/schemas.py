"""
Life-Link: Pydantic Schemas
Validates incoming request data and shapes API response data.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


# ==========================================
# DONOR SCHEMAS
# ==========================================

class DonorCreate(BaseModel):
    name: str = Field(..., example="Arun Kumar")
    phone: str = Field(..., example="+91 98765 43210")
    blood_group: str = Field(..., example="O+")
    city: Optional[str] = "Coimbatore"
    latitude: Optional[float] = 11.0168
    longitude: Optional[float] = 76.9558
    availability: Optional[str] = "AVAILABLE"  # AVAILABLE, MAYBE_AVAILABLE, UNAVAILABLE
    last_donation_date: Optional[date] = None
    donation_type: Optional[str] = "whole_blood"


class DonorResponse(BaseModel):
    id: int
    name: str
    phone: str
    blood_group: str
    city: str
    latitude: float
    longitude: float
    availability: str
    is_verified: bool
    last_donation_date: Optional[date] = None
    donation_type: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# EMERGENCY REQUEST SCHEMAS
# ==========================================

class EmergencyRequestCreate(BaseModel):
    hospital_name: str = Field(..., example="KMCH")
    blood_group: str = Field(..., example="O+")
    units_needed: int = Field(default=2, ge=1, example=2)
    patient_name: Optional[str] = "Emergency Patient"
    hospital_city: Optional[str] = "Coimbatore"
    latitude: Optional[float] = 11.0267
    longitude: Optional[float] = 77.0348
    resource_type: Optional[str] = "blood"
    component: Optional[str] = "whole_blood"
    urgency: Optional[str] = "CRITICAL"  # CRITICAL, URGENT, NORMAL
    contact_phone: str = Field(..., example="+91 94433 12345")
    notes: Optional[str] = None


class EmergencyRequestResponse(BaseModel):
    id: int
    patient_name: str
    hospital_name: str
    hospital_city: str
    latitude: float
    longitude: float
    resource_type: str
    component: str
    blood_group: str
    units_needed: int
    units_accepted: int
    urgency: str
    contact_phone: str
    status: str
    current_cascade_round: int
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# PHASE 2 MATCHING SCHEMAS
# ==========================================

class DonorMatchResponse(BaseModel):
    donor_id: int
    name: str
    blood_group: str
    distance_km: float
    availability: str
    phone_verified: bool
    approximate_location: Optional[str] = None


class EmergencyMatchesResponse(BaseModel):
    emergency_request_id: int
    hospital_name: str
    blood_group: str
    units_needed: int
    urgency: str
    total_compatible_found: int
    matches: List[DonorMatchResponse]
    message: str


# ==========================================
# PHASE 3 CASCADE SCHEMAS
# ==========================================

class CascadeRoundInfo(BaseModel):
    round: int
    radius: str
    min_distance_km: float
    max_distance_km: float
    new_matches: int
    cumulative_units_matched: int


class CascadeDonorMatch(BaseModel):
    donor_id: int
    name: str
    blood_group: str
    distance_km: float
    availability: str
    phone_verified: bool
    approximate_location: Optional[str] = None
    cascade_round: int


class CascadeResponse(BaseModel):
    emergency_request_id: int
    hospital_name: str
    blood_group: str
    units_required: int
    units_matched: int
    units_remaining: int
    status: str
    current_round: int
    blood_bank_backup_recommended: bool
    rounds: List[CascadeRoundInfo]
    matches: List[CascadeDonorMatch]
    message: str


# ==========================================
# PHASE 4 AI PARSER SCHEMAS
# ==========================================

class AIParseRequest(BaseModel):
    message: str = Field(..., example="KMCH la O positive blood 2 units urgent ah venum")
    auto_create: Optional[bool] = Field(default=False, description="If true and valid, automatically create the EmergencyRequest")
    contact_phone: Optional[str] = Field(default="+91 94433 00000", example="+91 94433 00000")


class AIParsedFields(BaseModel):
    resource_type: str = "blood"
    component: str = "whole_blood"
    blood_group: Optional[str] = None
    units_required: Optional[int] = None
    hospital_name: Optional[str] = None
    urgency: str = "NORMAL"
    contact_phone: Optional[str] = None


class AIParseResponse(BaseModel):
    success: bool
    parsed_request: AIParsedFields
    missing_fields: List[str]
    message: str
    created_emergency_request_id: Optional[int] = None
    emergency_request: Optional[EmergencyRequestResponse] = None


# ==========================================
# PHASE 5 FRONTEND / INTERACTION SCHEMAS
# ==========================================

class DonorResponseAction(BaseModel):
    donor_id: int
    action: str = Field(..., example="ACCEPT")  # ACCEPT or DECLINE


class DonorResponseResult(BaseModel):
    emergency_request_id: int
    donor_id: int
    action: str
    units_needed: int
    units_accepted: int
    status: str
    message: str


class DonorAvailabilityUpdate(BaseModel):
    availability: str = Field(..., example="AVAILABLE")  # AVAILABLE, MAYBE_AVAILABLE, UNAVAILABLE




