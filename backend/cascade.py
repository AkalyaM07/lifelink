"""
Life-Link: Adaptive Emergency Cascade Engine
Phase 3: Progressive radius expansion for emergency resource fulfillment.

Concept:
If an emergency cannot be fulfilled within the initial local radius (e.g. 0-5 km),
the cascade engine progressively expands the search perimeter:
  Round 1: 0 - 5 km   (Immediate vicinity)
  Round 2: 5 - 15 km  (Extended city zone)
  Round 3: 15 - 25 km (Greater metropolitan / district zone)
  Round 4: 25+ km     (Blood-bank & regional emergency resources)

Donors are deduplicated so no donor is contacted twice.
The cascade stops immediately as soon as the target required units are covered.
Respects and preserves distinct advanced states (DONOR_ACCEPTED, HOSPITAL_CONFIRMED, DONATION_COMPLETED).
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

import models
import matching


# =====================================================================
# CONFIGURABLE CASCADE CONFIGURATION
# =====================================================================
# Allows easy adjustment of search radii without changing business logic
DEFAULT_CASCADE_ROUNDS = [
    {"round": 1, "min_km": 0.0, "max_km": 5.0, "label": "0-5 km (Immediate Local)"},
    {"round": 2, "min_km": 5.0, "max_km": 15.0, "label": "5-15 km (Extended City)"},
    {"round": 3, "min_km": 15.0, "max_km": 25.0, "label": "15-25 km (Greater Metro)"},
]

BLOOD_BANK_FALLBACK_ROUND = 4
BLOOD_BANK_RADIUS_LABEL = "25+ km / Verified Blood Banks"


def execute_emergency_cascade(
    db: Session,
    emergency_request: models.EmergencyRequest,
    custom_rounds: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Executes progressive adaptive cascade for an emergency request.
    
    1. Checks each configured radius round sequentially.
    2. Uses matching engine to find compatible, available donors.
    3. Excludes donors already found in prior rounds.
    4. Stops immediately when required units are fulfilled (TARGET_REACHED).
    5. If all donor rounds are exhausted without reaching target:
       - Status is PARTIALLY_FULFILLED (if some donors found) or NO_MATCHES (if 0 donors found).
       - Flags blood_bank_backup_recommended = True.
    """
    units_required = emergency_request.units_needed
    if units_required <= 0:
        units_required = 1

    configured_rounds = custom_rounds or DEFAULT_CASCADE_ROUNDS

    matched_donors: List[Dict[str, Any]] = []
    seen_donor_ids = set()
    executed_rounds_info: List[Dict[str, Any]] = []
    
    current_round_num = 1
    target_reached = False

    for cfg in configured_rounds:
        r_num = cfg["round"]
        r_min = cfg["min_km"]
        r_max = cfg["max_km"]
        r_label = cfg["label"]

        current_round_num = r_num
        units_still_needed = units_required - len(matched_donors)

        # Query all compatible, available donors up to the maximum radius of this round
        candidates_result = matching.find_matches_for_request(
            db=db,
            emergency_request=emergency_request,
            max_distance_km=r_max
        )

        # Filter strictly for donors within [min_km, max_km) AND not seen in previous rounds
        new_donors_in_round = []
        for donor_data in candidates_result["matches"]:
            d_id = donor_data["donor_id"]
            d_dist = donor_data["distance_km"]

            # Must not be already matched in previous round
            if d_id in seen_donor_ids:
                continue

            # Must be within this round's distance band
            if d_dist >= r_min and d_dist <= r_max:
                seen_donor_ids.add(d_id)
                donor_entry = {
                    "donor_id": donor_data["donor_id"],
                    "name": donor_data["name"],
                    "blood_group": donor_data["blood_group"],
                    "distance_km": donor_data["distance_km"],
                    "availability": donor_data["availability"],
                    "phone_verified": donor_data["phone_verified"],
                    "approximate_location": donor_data["approximate_location"],
                    "cascade_round": r_num
                }
                new_donors_in_round.append(donor_entry)

        matched_donors.extend(new_donors_in_round)

        executed_rounds_info.append({
            "round": r_num,
            "radius": r_label,
            "min_distance_km": r_min,
            "max_distance_km": r_max,
            "new_matches": len(new_donors_in_round),
            "cumulative_units_matched": min(len(matched_donors), units_required)
        })

        # Check if target requirement is covered
        if len(matched_donors) >= units_required:
            target_reached = True
            break

    # Determine cascade outcome status
    units_matched = min(len(matched_donors), units_required)
    units_remaining = max(0, units_required - len(matched_donors))

    if len(matched_donors) == 0:
        status = "NO_MATCHES"
        message = "No compatible available donors found in any search radius. Immediate blood bank escalation required."
        blood_bank_needed = True
    elif target_reached:
        status = "TARGET_REACHED"
        message = f"Target reached! Found {len(matched_donors)} compatible donor(s) covering {units_required} required unit(s) within Round {current_round_num}."
        blood_bank_needed = False
    else:
        status = "PARTIALLY_FULFILLED"
        message = f"Partially fulfilled. Found {len(matched_donors)} donor(s), but {units_remaining} unit(s) are still needed. Blood bank resources recommended."
        blood_bank_needed = True
        current_round_num = BLOOD_BANK_FALLBACK_ROUND

    # Update database record status and current round
    # Preserve advanced lifecycle states (e.g. if a donor already accepted or hospital confirmed)
    emergency_request.current_cascade_round = current_round_num
    advanced_states = [
        "DONOR_ACCEPTED", "HOSPITAL_CONFIRMED", "SCREENING_PENDING",
        "SCREENING_COMPLETED", "DONATION_IN_PROGRESS", "DONATION_COMPLETED"
    ]
    if emergency_request.status not in advanced_states:
        emergency_request.status = status
    db.commit()

    return {
        "emergency_request_id": emergency_request.id,
        "hospital_name": emergency_request.hospital_name,
        "blood_group": emergency_request.blood_group,
        "units_required": units_required,
        "units_matched": len(matched_donors),
        "units_remaining": units_remaining,
        "status": emergency_request.status,
        "current_round": current_round_num,
        "blood_bank_backup_recommended": blood_bank_needed,
        "rounds": executed_rounds_info,
        "matches": matched_donors,
        "message": message
    }
