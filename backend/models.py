"""
Life-Link: SQLAlchemy Database Models
Unified User Account Architecture & Emergency Coordination Models.

Core Models:
- User: Central identity for both requesting and donating blood, with notifications, responses, donations.
- Donor: Backward-compatible donor record used by existing test suites & matching engine.
- EmergencyRequest: Central emergency model associated with user_id & distinguishing patient from requester.
- DonorResponse: Track willing / accepted / declined responses associated with user & emergency.
- Notification: Verified backend notification events per user.
- Donation: Verified completed donation history & cooldown review tracking.
"""

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    """
    Central User Identity.
    One normal user account that can request blood, donate blood, receive notifications,
    view donation history, and respond to alerts.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)  # Secure PBKDF2 hash, never plain-text
    
    blood_group = Column(String, nullable=False, default="O+")
    location = Column(String, default="Coimbatore")
    latitude = Column(Float, nullable=False, default=11.0168)
    longitude = Column(Float, nullable=False, default=76.9558)
    
    # Availability: 'AVAILABLE', 'UNAVAILABLE', 'REVIEW_NEEDED'
    availability = Column(String, default="AVAILABLE")
    
    # Eligibility & donation history tracking
    last_donation_date = Column(Date, nullable=True)
    donation_type = Column(String, default="whole_blood")  # whole_blood, platelets, plasma, rbc
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    emergency_requests = relationship("EmergencyRequest", back_populates="user", foreign_keys="EmergencyRequest.user_id")
    donor_responses = relationship("DonorResponse", back_populates="user", foreign_keys="DonorResponse.user_id")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan", foreign_keys="Notification.user_id")
    donations = relationship("Donation", back_populates="user", cascade="all, delete-orphan", foreign_keys="Donation.user_id")


class Donor(Base):
    """
    Represents a registered voluntary blood donor.
    Preserved for full backward compatibility with Phase 1-5 endpoints & test suites.
    Linked optionally to a central User ID.
    """
    __tablename__ = "donors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    blood_group = Column(String, nullable=False)  # e.g., 'O+', 'A+', 'B+', 'AB-', etc.
    
    # Location information for proximity matching
    city = Column(String, default="Coimbatore")
    latitude = Column(Float, nullable=False, default=11.0168)
    longitude = Column(Float, nullable=False, default=76.9558)
    
    # Availability: 'AVAILABLE', 'MAYBE_AVAILABLE', 'UNAVAILABLE', 'REVIEW_NEEDED'
    availability = Column(String, default="AVAILABLE")
    
    # Verification status (simulated OTP / admin check)
    is_verified = Column(Boolean, default=True)
    
    # Eligibility tracking
    last_donation_date = Column(Date, nullable=True)
    donation_type = Column(String, default="whole_blood")  # whole_blood, platelets, plasma, rbc
    
    # Optional link to central User
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class EmergencyRequest(Base):
    """
    Represents an emergency medical resource request (e.g. blood requirement at a hospital).
    Distinguishes the account holder (requester_name / user_id) from the patient (patient_name).
    """
    __tablename__ = "emergency_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    requester_name = Column(String, nullable=True)  # Account holder name e.g. "Akalya"
    patient_name = Column(String, default="Emergency Patient")  # Patient name e.g. "Sathya"
    
    hospital_name = Column(String, nullable=False)  # e.g., 'KMCH', 'PSG Hospitals', 'GKNM'
    hospital_city = Column(String, default="Coimbatore")
    
    # Hospital location coordinates
    latitude = Column(Float, default=11.0267)
    longitude = Column(Float, default=77.0348)
    
    # Resource details
    resource_type = Column(String, default="blood")  # 'blood', 'organ', 'tissue'
    component = Column(String, default="whole_blood")  # 'whole_blood', 'packed_rbc', 'platelets', 'plasma'
    blood_group = Column(String, nullable=False)  # e.g., 'O+'
    units_needed = Column(Integer, nullable=False, default=1)
    units_accepted = Column(Integer, default=0)
    
    # Priority & lifecycle status:
    # 'REQUEST_CREATED', 'SEARCHING', 'COMPATIBLE_DONORS_FOUND', 'WAITING_FOR_RESPONSES',
    # 'DONOR_ACCEPTED', 'HOSPITAL_CONFIRMED', 'SCREENING_PENDING', 'SCREENING_COMPLETED',
    # 'DONATION_IN_PROGRESS', 'DONATION_COMPLETED', 'TARGET_REACHED', 'PARTIALLY_FULFILLED', 'NO_MATCHES'
    urgency = Column(String, default="CRITICAL")  # 'CRITICAL', 'URGENT', 'NORMAL'
    contact_phone = Column(String, nullable=False)
    status = Column(String, default="SEARCHING")
    
    # Distinct lifecycle state flags
    hospital_confirmed = Column(Boolean, default=False)
    screening_status = Column(String, default="PENDING")  # PENDING, PASSED, FAILED
    donation_completed = Column(Boolean, default=False)
    
    # Adaptive cascade tracking (starts at Round 1: 0-5km)
    current_cascade_round = Column(Integer, default=1)
    
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="emergency_requests", foreign_keys=[user_id])
    responses = relationship("DonorResponse", back_populates="emergency_request", cascade="all, delete-orphan")


class DonorResponse(Base):
    """
    Represents a donor's voluntary response to an emergency request.
    Distinct from hospital confirmation and donation completion.
    """
    __tablename__ = "donor_responses"

    id = Column(Integer, primary_key=True, index=True)
    emergency_request_id = Column(Integer, ForeignKey("emergency_requests.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    donor_id = Column(Integer, nullable=True)  # Backward compat for legacy donor IDs
    donor_name = Column(String, nullable=False)
    blood_group = Column(String, nullable=False)
    action = Column(String, nullable=False)  # "ACCEPT" or "DECLINE"
    
    # Detailed lifecycle state: "WILLING", "DECLINED", "HOSPITAL_CONFIRMED", "SCREENING_PASSED", "DONATION_COMPLETED"
    status = Column(String, default="WILLING")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="donor_responses", foreign_keys=[user_id])
    emergency_request = relationship("EmergencyRequest", back_populates="responses", foreign_keys=[emergency_request_id])


class Notification(Base):
    """
    Verified backend notification record for a user.
    Types: EMERGENCY_ALERT, CASCADE_UPDATE, HOSPITAL_UPDATE, SCREENING_UPDATE, DONATION_COMPLETED
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    emergency_request_id = Column(Integer, ForeignKey("emergency_requests.id"), nullable=True)
    type = Column(String, nullable=False)  # EMERGENCY_ALERT, CASCADE_UPDATE, HOSPITAL_UPDATE, SCREENING_UPDATE, DONATION_COMPLETED
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="notifications", foreign_keys=[user_id])


class Donation(Base):
    """
    Verified record of a completed blood donation.
    Updates donor availability and triggers eligibility review timeline.
    """
    __tablename__ = "donations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    emergency_request_id = Column(Integer, ForeignKey("emergency_requests.id"), nullable=True)
    donor_id = Column(Integer, nullable=True)
    hospital_name = Column(String, nullable=False)
    blood_group = Column(String, nullable=False)
    component = Column(String, default="whole_blood")
    units = Column(Integer, default=1)
    donation_date = Column(Date, default=date.today)
    status = Column(String, default="COMPLETED")
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="donations", foreign_keys=[user_id])
