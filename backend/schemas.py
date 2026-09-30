"""
Life-Link: Pydantic Schemas
Validates incoming request data and shapes API response data.
Preserves all Phase 1-5 schemas while adding unified User, Notification,
Donation, and enhanced AI conversational interaction schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


# ==========================================
# USER SCHEMAS (SINGLE CENTRAL ACCOUNT)
# ==========================================

class UserCreate(BaseModel):
    name: str = Field(..., example="Akalya M")
    email: str = Field(..., example="akalya@example.com")
    phone: str = Field(..., example="+91 94433 12345")
    password: str = Field(..., min_length=4, example="secret123")
    blood_group: str = Field(default="O+", example="O+")
    location: Optional[str] = "Coimbatore"
    latitude: Optional[float] = 11.0168
    longitude: Optional[float] = 76.9558
    availability: Optional[str] = "AVAILABLE"  # AVAILABLE, UNAVAILABLE, REVIEW_NEEDED
    donation_type: Optional[str] = "whole_blood"


class UserLogin(BaseModel):
    email: str = Field(..., example="akalya@example.com")
    password: str = Field(..., example="secret123")


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    blood_group: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    availability: Optional[str] = None
    donation_type: Optional[str] = None


class UserAvailabilityUpdate(BaseModel):
    availability: str = Field(..., example="AVAILABLE")  # AVAILABLE, UNAVAILABLE, REVIEW_NEEDED


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    blood_group: str
    location: str
    latitude: float
    longitude: float
    availability: str
    last_donation_date: Optional[date] = None
    donation_type: str
    created_at: datetime
    next_review_date: Optional[date] = None
    eligibility_status_message: Optional[str] = None

    class Config:
        from_attributes = True


# ==========================================
# DONOR SCHEMAS (PHASE 1-5 COMPATIBILITY)
# ==========================================

class DonorCreate(BaseModel):
    name: str = Field(..., example="Arun Kumar")
    phone: str = Field(..., example="+91 98765 43210")
    blood_group: str = Field(..., example="O+")
    city: Optional[str] = "Coimbatore"
    latitude: Optional[float] = 11.0168
    longitude: Optional[float] = 76.9558
    availability: Optional[str] = "AVAILABLE"  # AVAILABLE, MAYBE_AVAILABLE, UNAVAILABLE, REVIEW_NEEDED
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
    user_id: Optional[int] = None
    requester_name: Optional[str] = None


class EmergencyRequestResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    requester_name: Optional[str] = None
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
    hospital_confirmed: Optional[bool] = False
    screening_status: Optional[str] = "PENDING"
    donation_completed: Optional[bool] = False
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
    user_id: Optional[int] = None
    response_status: Optional[str] = None


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
# PHASE 4 AI PARSER & BOT SCHEMAS
# ==========================================

class AIParseRequest(BaseModel):
    message: str = Field(..., example="KMCH la O positive blood 2 units urgent ah venum")
    auto_create: Optional[bool] = Field(default=False, description="If true and valid, automatically create the EmergencyRequest")
    contact_phone: Optional[str] = Field(default="+91 94433 00000", example="+91 94433 00000")
    user_id: Optional[int] = None
    requester_name: Optional[str] = None


class AIParsedFields(BaseModel):
    resource_type: str = "blood"
    component: str = "whole_blood"
    blood_group: Optional[str] = None
    units_required: Optional[int] = None
    hospital_name: Optional[str] = None
    urgency: str = "NORMAL"
    contact_phone: Optional[str] = None
    patient_name: Optional[str] = "Emergency Patient"
    requester_name: Optional[str] = None


class AIParseResponse(BaseModel):
    success: bool
    parsed_request: AIParsedFields
    missing_fields: List[str]
    message: str
    created_emergency_request_id: Optional[int] = None
    emergency_request: Optional[EmergencyRequestResponse] = None


class AIChatMessage(BaseModel):
    message: str = Field(..., example="My father Sathya needs 2 units O+ blood at KMCH urgently.")
    user_id: Optional[int] = None
    requester_name: Optional[str] = None
    active_emergency_id: Optional[int] = None
    accumulated_fields: Optional[Dict[str, Any]] = None


class AIChatResponse(BaseModel):
    reply: str
    ready_for_confirmation: bool
    extracted_fields: AIParsedFields
    missing_fields: List[str]
    confirmation_card: Optional[Dict[str, Any]] = None
    backend_status: Optional[Dict[str, Any]] = None


# ==========================================
# PHASE 5 & NEW INTERACTION SCHEMAS
# ==========================================

class DonorResponseAction(BaseModel):
    donor_id: Optional[int] = None
    user_id: Optional[int] = None
    action: str = Field(..., example="ACCEPT")  # ACCEPT or DECLINE


class DonorResponseResult(BaseModel):
    emergency_request_id: int
    donor_id: Optional[int] = None
    user_id: Optional[int] = None
    action: str
    units_needed: int
    units_accepted: int
    status: str
    message: str


class DonorAvailabilityUpdate(BaseModel):
    availability: str = Field(..., example="AVAILABLE")  # AVAILABLE, MAYBE_AVAILABLE, UNAVAILABLE


class DonorResponseDetail(BaseModel):
    id: int
    emergency_request_id: int
    user_id: Optional[int] = None
    donor_id: Optional[int] = None
    donor_name: str
    blood_group: str
    action: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# NOTIFICATION SCHEMAS
# ==========================================

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    emergency_request_id: Optional[int] = None
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# DONATION & ELIGIBILITY SCHEMAS
# ==========================================

class HospitalConfirmRequest(BaseModel):
    notes: Optional[str] = None


class ScreeningUpdateRequest(BaseModel):
    donor_user_id: int
    passed: bool = True
    notes: Optional[str] = None


class CompleteDonationRequest(BaseModel):
    donor_user_id: int
    units: Optional[int] = 1
    units_donated: Optional[int] = None
    notes: Optional[str] = None


class DonationCreate(BaseModel):
    user_id: int
    emergency_request_id: Optional[int] = None
    hospital_name: str
    blood_group: str
    component: Optional[str] = "whole_blood"
    units: Optional[int] = 1
    donation_date: Optional[date] = None
    notes: Optional[str] = None


class DonationResponse(BaseModel):
    id: int
    user_id: int
    emergency_request_id: Optional[int] = None
    hospital_name: str
    blood_group: str
    component: str
    units: int
    donation_date: date
    status: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# MATCHED FEED SCHEMA (BLOOD REQUESTS I CAN HELP WITH)
# ==========================================

class MatchedEmergencyFeedItem(BaseModel):
    emergency_request_id: int
    hospital_name: str
    hospital_city: str
    blood_group: str
    component: str
    units_needed: int
    units_accepted: int
    urgency: str
    status: str
    distance_km: float
    requester_name: Optional[str] = None
    patient_name: str
    has_user_responded: bool = False
    user_action: Optional[str] = None
    created_at: datetime
