"""
Life-Link: Verified Backend Notification Service
Creates and distributes privacy-safe notifications to users based strictly on real backend events.
Does NOT fabricate notifications.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import models


def notify_compatible_available_donors(
    db: Session,
    emergency_request: models.EmergencyRequest,
    matched_donors: List[Dict[str, Any]],
    round_num: int = 1
) -> int:
    """
    Notifies ALL relevant compatible available donors when an emergency request is confirmed
    or when a cascade round expands.
    Creates a real record in the notifications table for each registered user.
    """
    count = 0
    # Map donor IDs and user IDs to notify
    for donor_data in matched_donors:
        user_id = donor_data.get("user_id")
        donor_id = donor_data.get("donor_id")
        
        # If user_id not in match record, look up in Donor model
        if not user_id and donor_id:
            d_obj = db.query(models.Donor).filter(models.Donor.id == donor_id).first()
            if d_obj and d_obj.user_id:
                user_id = d_obj.user_id

        # If we have a user identity, check if they already received an alert for this emergency
        if user_id:
            existing = db.query(models.Notification).filter(
                models.Notification.user_id == user_id,
                models.Notification.emergency_request_id == emergency_request.id,
                models.Notification.type == "EMERGENCY_ALERT"
            ).first()

            if not existing:
                dist_str = f" (~{donor_data.get('distance_km', 0.0)} km away)" if donor_data.get('distance_km') is not None else ""
                notif = models.Notification(
                    user_id=user_id,
                    emergency_request_id=emergency_request.id,
                    type="EMERGENCY_ALERT",
                    title=f"🩸 Emergency Blood Request ({emergency_request.blood_group})",
                    message=(
                        f"You may be able to help with an {emergency_request.blood_group} emergency at "
                        f"{emergency_request.hospital_name}{dist_str}. "
                        f"{emergency_request.units_needed} unit(s) needed for patient {emergency_request.patient_name}."
                    )
                )
                db.add(notif)
                count += 1

    if count > 0:
        db.commit()
    return count


def notify_cascade_update(
    db: Session,
    emergency_request: models.EmergencyRequest,
    round_num: int,
    radius_label: str,
    new_matches_count: int
):
    """
    Notifies the requester when cascade expands to a new search perimeter.
    """
    if not emergency_request.user_id:
        return

    notif = models.Notification(
        user_id=emergency_request.user_id,
        emergency_request_id=emergency_request.id,
        type="CASCADE_UPDATE",
        title=f"🔄 Cascade Update: Round {round_num}",
        message=(
            f"Emergency search perimeter expanded to Round {round_num} ({radius_label}). "
            f"{new_matches_count} additional candidate donors found."
        )
    )
    db.add(notif)
    db.commit()


def notify_hospital_confirmation(
    db: Session,
    emergency_request: models.EmergencyRequest,
    hospital_message: str
):
    """
    Notifies the requester and accepted donors of hospital confirmation.
    """
    # Notify requester
    if emergency_request.user_id:
        notif = models.Notification(
            user_id=emergency_request.user_id,
            emergency_request_id=emergency_request.id,
            type="HOSPITAL_UPDATE",
            title="🏥 Hospital Confirmation Received",
            message=hospital_message
        )
        db.add(notif)

    # Notify accepted donors
    responses = db.query(models.DonorResponse).filter(
        models.DonorResponse.emergency_request_id == emergency_request.id,
        models.DonorResponse.action == "ACCEPT"
    ).all()

    for resp in responses:
        if resp.user_id and resp.user_id != emergency_request.user_id:
            donor_notif = models.Notification(
                user_id=resp.user_id,
                emergency_request_id=emergency_request.id,
                type="HOSPITAL_UPDATE",
                title="🏥 Hospital Verified Your Response",
                message=f"{emergency_request.hospital_name} has verified the requirement and scheduled donor coordination."
            )
            db.add(donor_notif)

    db.commit()


def notify_screening_update(
    db: Session,
    emergency_request: models.EmergencyRequest,
    donor_user_id: int,
    passed: bool
):
    """
    Notifies a donor regarding clinical screening outcome.
    """
    status_text = "passed clinical screening" if passed else "not eligible for donation today per medical review"
    notif = models.Notification(
        user_id=donor_user_id,
        emergency_request_id=emergency_request.id,
        type="SCREENING_UPDATE",
        title="🩺 Clinical Screening Update",
        message=f"You have {status_text} at {emergency_request.hospital_name}. Final suitability is managed by the clinical blood bank."
    )
    db.add(notif)
    db.commit()


def notify_donation_completion(
    db: Session,
    user_id: int,
    emergency_request_id: Optional[int],
    hospital_name: str,
    blood_group: str,
    units: int
):
    """
    Notifies donor upon verified completed donation.
    """
    notif = models.Notification(
        user_id=user_id,
        emergency_request_id=emergency_request_id,
        type="DONATION_COMPLETED",
        title="🟢 Donation Record Completed",
        message=(
            f"Thank you for donating {units} unit(s) of {blood_group} blood at {hospital_name}! "
            f"Your donation record has been updated and a new eligibility review date has been scheduled."
        )
    )
    db.add(notif)
    db.commit()
