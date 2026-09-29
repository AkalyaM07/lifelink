"""
Life-Link: SQLAlchemy Database Models
Simple and readable models representing Donors and Emergency Requests.
"""

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime
from database import Base


class Donor(Base):
    """
    Represents a registered voluntary blood donor.
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
    
    # Availability: 'AVAILABLE', 'MAYBE_AVAILABLE', 'UNAVAILABLE'
    availability = Column(String, default="AVAILABLE")
    
    # Verification status (simulated OTP / admin check)
    is_verified = Column(Boolean, default=True)
    
    # Eligibility tracking
    last_donation_date = Column(Date, nullable=True)
    donation_type = Column(String, default="whole_blood")  # whole_blood, platelets, plasma, rbc
    
    created_at = Column(DateTime, default=datetime.utcnow)


class EmergencyRequest(Base):
    """
    Represents an emergency medical resource request (e.g. blood requirement at a hospital).
    """
    __tablename__ = "emergency_requests"

    id = Column(Integer, primary_key=True, index=True)
    patient_name = Column(String, default="Emergency Patient")
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
    
    # Priority & status
    urgency = Column(String, default="CRITICAL")  # 'CRITICAL', 'URGENT', 'NORMAL'
    contact_phone = Column(String, nullable=False)
    status = Column(String, default="SEARCHING")  # 'REQUEST_CREATED', 'SEARCHING', 'TARGET_REACHED', 'COMPLETED'
    
    # Adaptive cascade tracking (starts at Round 1: 0-5km)
    current_cascade_round = Column(Integer, default=1)
    
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
