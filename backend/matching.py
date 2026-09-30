"""
Life-Link: Intelligent Medical Resource Matching Engine
Phase 2 & Unified Single-User Matching Architecture
Blood Compatibility, Availability Filtering, Haversine Distance, and Matched Emergency Feed

DISCLAIMER:
This is a software coordination prototype. It does NOT replace clinical
blood-bank cross-matching or compatibility tests. All transfusion procedures
must be verified by qualified medical professionals.
"""

import math
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import models


# =====================================================================
# 1. BLOOD GROUP COMPATIBILITY MATRIX
# =====================================================================
# Red Blood Cell compatibility chart:
# For each recipient blood group, lists which donor blood groups are compatible.
BLOOD_COMPATIBILITY: Dict[str, List[str]] = {
    # O Negative is Universal Red Cell Donor
    "O-": ["O-"],
    "O+": ["O+", "O-"],
    
    # A Types
    "A-": ["A-", "O-"],
    "A+": ["A+", "A-", "O+", "O-"],
    
    # B Types
    "B-": ["B-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    
    # AB Types (AB+ is Universal Red Cell Recipient)
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"]
}

# Reverse compatibility: For a donor's blood group, which recipient blood groups can they donate to
DONOR_CAN_GIVE_TO: Dict[str, List[str]] = {
    "O-": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "O+": ["O+", "A+", "B+", "AB+"],
    "A-": ["A-", "A+", "AB-", "AB+"],
    "A+": ["A+", "AB+"],
    "B-": ["B-", "B+", "AB-", "AB+"],
    "B+": ["B+", "AB+"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB+"]
}

# Configurable donation cooldown days by component
# Final eligibility is always determined by the medical / blood-bank team
CONFIGURABLE_COOLDOWN_DAYS: Dict[str, int] = {
    "whole_blood": 90,
    "packed_rbc": 90,
    "platelets": 14,
    "plasma": 28
}


def get_compatible_donor_groups(recipient_blood_group: str) -> List[str]:
    """
    Returns list of compatible donor blood groups for a given recipient.
    Case-insensitive and handles trailing spaces/plus signs.
    """
    clean_group = recipient_blood_group.strip().upper()
    return BLOOD_COMPATIBILITY.get(clean_group, [])


def get_recipient_groups_donor_can_help(donor_blood_group: str) -> List[str]:
    """
    Returns list of recipient blood groups that a given donor blood group can help.
    """
    clean_group = donor_blood_group.strip().upper()
    return DONOR_CAN_GIVE_TO.get(clean_group, [])


# =====================================================================
# 2. HAVERSINE DISTANCE CALCULATION
# =====================================================================

def haversine_distance(lat1: Optional[float], lon1: Optional[float], 
                       lat2: Optional[float], lon2: Optional[float]) -> float:
    """
    Calculates great-circle distance between two geographic coordinates on Earth.
    Formula: Haversine
    Radius of Earth: ~6371.0 km
    Returns: Distance in kilometers (km).
    Gracefully returns infinity (99999.0) if coordinates are missing or invalid.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 99999.0

    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        
        # Convert decimal degrees to radians
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        
        r_lat1 = math.radians(lat1)
        r_lat2 = math.radians(lat2)

        # Haversine formula
        a = (math.sin(d_lat / 2) ** 2 +
             math.cos(r_lat1) * math.cos(r_lat2) * math.sin(d_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        radius_km = 6371.0
        return round(radius_km * c, 2)
    except (ValueError, TypeError):
        return 99999.0


# =====================================================================
# 3. ELIGIBILITY / COOLDOWN REMINDER CALCULATION
# =====================================================================

def calculate_eligibility_reminder(
    last_donation_date: Optional[date],
    donation_type: str = "whole_blood",
    custom_cooldown_days: Optional[int] = None
) -> Dict[str, Any]:
    """
    Calculates the next review/reminder date for a donor based on configurable rules.
    Does NOT hard-code universal medical absolutes:
    clearly notes that final eligibility is determined by the hospital/blood-bank team.
    """
    cooldown = custom_cooldown_days or CONFIGURABLE_COOLDOWN_DAYS.get(donation_type.lower(), 90)
    
    if not last_donation_date:
        return {
            "has_donated_before": False,
            "last_donation_date": None,
            "next_review_date": None,
            "cooldown_days": cooldown,
            "is_system_available": True,
            "status_message": "You may be able to respond to eligible blood requests. Final clinical eligibility is determined by the hospital or blood bank team upon arrival."
        }

    next_review = last_donation_date + timedelta(days=cooldown)
    today = date.today()
    days_remaining = (next_review - today).days

    if days_remaining > 0:
        return {
            "has_donated_before": True,
            "last_donation_date": last_donation_date,
            "next_review_date": next_review,
            "cooldown_days": cooldown,
            "is_system_available": False,
            "status_message": f"Recent donation recorded on {last_donation_date.strftime('%d %B %Y')}. Configured review period is {cooldown} days. Estimated next review: {next_review.strftime('%d %B %Y')} ({days_remaining} day(s) remaining). Final eligibility is determined by the medical/blood-bank team."
        }
    else:
        return {
            "has_donated_before": True,
            "last_donation_date": last_donation_date,
            "next_review_date": next_review,
            "cooldown_days": cooldown,
            "is_system_available": True,
            "status_message": f"Review period completed ({cooldown} days since {last_donation_date.strftime('%d %B %Y')}). You may be able to respond to eligible blood requests. Final eligibility is determined by the medical/blood-bank team."
        }


# =====================================================================
# 4. MATCHING ENGINE CORE (FOR EMERGENCY REQUEST)
# =====================================================================

def find_matches_for_request(
    db: Session,
    emergency_request: models.EmergencyRequest,
    max_distance_km: Optional[float] = None,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Finds and ranks compatible available donors for an active emergency request.
    
    Filters applied:
    1. Blood group compatibility (recipient vs donor)
    2. Availability status must be 'AVAILABLE'
    3. Distance from emergency hospital
    4. Optional maximum radius (used in cascade rounds)
    
    Ranking:
    - Sorted by distance ascending (closest donors first)
    Privacy safe:
    - Never exposes exact address or private phone number.
    """
    recipient_group = emergency_request.blood_group.strip().upper()
    compatible_groups = get_compatible_donor_groups(recipient_group)

    if not compatible_groups:
        return {
            "emergency_request_id": emergency_request.id,
            "hospital_name": emergency_request.hospital_name,
            "blood_group": emergency_request.blood_group,
            "units_needed": emergency_request.units_needed,
            "urgency": emergency_request.urgency,
            "total_compatible_found": 0,
            "matches": [],
            "message": f"Invalid or unsupported recipient blood group: '{emergency_request.blood_group}'"
        }

    # Query donors who have compatible blood groups and are marked 'AVAILABLE'
    candidate_donors = db.query(models.Donor).filter(
        models.Donor.blood_group.in_(compatible_groups),
        models.Donor.availability == "AVAILABLE"
    ).all()

    # Pre-fetch any existing responses for this request to check status
    existing_responses = {
        r.donor_id: r.status
        for r in db.query(models.DonorResponse).filter(
            models.DonorResponse.emergency_request_id == emergency_request.id
        ).all()
        if r.donor_id is not None
    }

    matches = []
    for donor in candidate_donors:
        # Calculate approximate distance from emergency hospital
        dist = haversine_distance(
            emergency_request.latitude,
            emergency_request.longitude,
            donor.latitude,
            donor.longitude
        )

        # If a max distance threshold is specified, enforce it
        if max_distance_km is not None and dist > max_distance_km:
            continue

        # Check donor eligibility if last_donation_date is available
        eligibility = calculate_eligibility_reminder(donor.last_donation_date, donor.donation_type or "whole_blood")
        if not eligibility["is_system_available"]:
            # Cooldown not met, skip donor from active matches
            continue

        # Response status if already responded
        resp_status = existing_responses.get(donor.id, "WAITING")

        # Build clean donor match record without exposing private address or full phone
        matches.append({
            "donor_id": donor.id,
            "name": donor.name,
            "blood_group": donor.blood_group,
            "distance_km": dist,
            "availability": donor.availability,
            "phone_verified": donor.is_verified,
            "approximate_location": donor.city,
            "user_id": donor.user_id,
            "response_status": resp_status
        })

    # Sort primarily by proximity (closest donor first)
    matches.sort(key=lambda m: m["distance_km"])

    if limit is not None and limit > 0:
        matches = matches[:limit]

    message = (
        f"Found {len(matches)} suitable available donor(s) nearby."
        if matches else "No suitable donors found nearby."
    )

    return {
        "emergency_request_id": emergency_request.id,
        "hospital_name": emergency_request.hospital_name,
        "blood_group": emergency_request.blood_group,
        "units_needed": emergency_request.units_needed,
        "urgency": emergency_request.urgency,
        "total_compatible_found": len(matches),
        "matches": matches,
        "message": message
    }


# =====================================================================
# 5. MATCHED BLOOD REQUEST FEED FOR USERS (BLOOD REQUESTS I CAN HELP WITH)
# =====================================================================

def find_matched_emergencies_for_user(
    db: Session,
    user: models.User,
    max_distance_km: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Finds active emergency requests that the current user may be able to help with
    according to biological blood compatibility and donor availability.
    Creates the second donor discovery path (User opens account -> Voluntary response).
    """
    # If user is marked UNAVAILABLE or REVIEW_NEEDED, they cannot respond
    if user.availability != "AVAILABLE":
        return []

    # Check eligibility cooldown
    eligibility = calculate_eligibility_reminder(user.last_donation_date, user.donation_type or "whole_blood")
    if not eligibility["is_system_available"]:
        return []

    user_blood = (user.blood_group or "O+").strip().upper()
    recipient_groups_can_help = get_recipient_groups_donor_can_help(user_blood)

    if not recipient_groups_can_help:
        return []

    # Query active emergency requests
    active_statuses = [
        "SEARCHING", "COMPATIBLE_DONORS_FOUND", "WAITING_FOR_RESPONSES",
        "PARTIALLY_FULFILLED", "DONOR_ACCEPTED"
    ]
    candidate_requests = db.query(models.EmergencyRequest).filter(
        models.EmergencyRequest.blood_group.in_(recipient_groups_can_help),
        models.EmergencyRequest.status.in_(active_statuses)
    ).all()

    # Pre-fetch user's previous responses
    user_responses = {
        r.emergency_request_id: r.action
        for r in db.query(models.DonorResponse).filter(
            models.DonorResponse.user_id == user.id
        ).all()
    }

    matched_feed = []
    for req in candidate_requests:
        # Distance calculation
        dist = haversine_distance(
            req.latitude,
            req.longitude,
            user.latitude,
            user.longitude
        )

        if max_distance_km is not None and dist > max_distance_km:
            continue

        has_responded = req.id in user_responses
        user_action = user_responses.get(req.id)

        matched_feed.append({
            "emergency_request_id": req.id,
            "hospital_name": req.hospital_name,
            "hospital_city": req.hospital_city or "Coimbatore",
            "blood_group": req.blood_group,
            "component": req.component or "whole_blood",
            "units_needed": req.units_needed,
            "units_accepted": req.units_accepted,
            "urgency": req.urgency,
            "status": req.status,
            "distance_km": dist,
            "requester_name": req.requester_name,
            "patient_name": req.patient_name,
            "has_user_responded": has_responded,
            "user_action": user_action,
            "created_at": req.created_at
        })

    # Sort closest first
    matched_feed.sort(key=lambda item: item["distance_km"])
    return matched_feed
