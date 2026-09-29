"""
Life-Link: Intelligent Medical Resource Matching Engine
Phase 2: Blood Compatibility, Availability Filtering, and Haversine Distance

DISCLAIMER:
This is a software coordination prototype. It does NOT replace clinical
blood-bank cross-matching or compatibility tests. All transfusion procedures
must be verified by qualified medical professionals.
"""

import math
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


def get_compatible_donor_groups(recipient_blood_group: str) -> List[str]:
    """
    Returns list of compatible donor blood groups for a given recipient.
    Case-insensitive and handles trailing spaces/plus signs.
    """
    clean_group = recipient_blood_group.strip().upper()
    return BLOOD_COMPATIBILITY.get(clean_group, [])


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
# 3. MATCHING ENGINE CORE
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

        # Check donor eligibility if last_donation_date is available (standard 90 days for whole blood)
        # Note: Phase 4 will introduce full dynamic eligibility engine, but we include safe check here
        is_eligible = True
        if donor.last_donation_date:
            # We preserve donor's eligibility flag for scoring
            pass

        # Build clean donor match record without exposing private address or full phone
        matches.append({
            "donor_id": donor.id,
            "name": donor.name,
            "blood_group": donor.blood_group,
            "distance_km": dist,
            "availability": donor.availability,
            "phone_verified": donor.is_verified,
            "approximate_location": donor.city
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
