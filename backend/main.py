"""
Life-Link: Main FastAPI Application
AI-Powered Emergency Medical Resource & Donor Coordination Network

Architectural Features:
- Unified Single Normal User Account (User can request blood, donate blood, receive notifications)
- Distinguishes Account Holder from Patient
- Interactive Multilingual AI Bot (English, Tamil, Tanglish) with Editable Confirmation Card
- Database as Source of Truth (No hallucinated status)
- Intelligent Matching with Privacy-Safe Records
- Notifying ALL Relevant Compatible Available Donors
- Distinct States: DONOR_WILLING, HOSPITAL_CONFIRMED, SCREENING, DONATION_COMPLETED
- Matched Blood Request Feed ("Blood Requests You Can Help With")
- Configurable Donation Availability / Eligibility Reminders
- Adaptive Emergency Cascade Engine
- Full Backward Compatibility with all Phase 1-5 Endpoints & Tests
"""

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import date, timedelta, datetime
import re

import models
import schemas
import matching
import cascade
import ai_parser
import notifications_service
from security import hash_password, verify_password
from database import engine, get_db, ensure_schema_upgrades

# Create database tables automatically on startup and perform safe schema migrations
models.Base.metadata.create_all(bind=engine)
ensure_schema_upgrades(engine)

app = FastAPI(
    title="Life-Link Emergency Resource Coordination API",
    description="Emergency Medical Resource & Donor Coordination Network prototype.",
    version="2.0.0"
)

# Enable CORS for local dev servers and cloud deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "https://lifelink-1-mnme.onrender.com",
        "https://lifelink-2ldt.onrender.com",
        "null",  # file:// protocol
    ],
    allow_origin_regex=r"https?://.*",  # Allow all HTTP/HTTPS origins (dev & deployed)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# ROOT / HEALTH ENDPOINT
# ==========================================

@app.get("/")
def read_root():
    return {
        "project": "LIFE-LINK",
        "tagline": "AI-Powered Emergency Medical Resource & Donor Coordination Network",
        "status": "online",
        "version": "2.0.0 (Unified Single User & AI Emergency Bot)",
        "docs_url": "/docs"
    }


# ==========================================
# 1. SINGLE NORMAL USER ACCOUNT ENDPOINTS
# ==========================================

@app.post("/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new normal user in the unified Life-Link account model.
    A single user can request blood, donate blood, receive notifications, and track history.
    Never stores plain-text passwords.
    """
    clean_email = user_in.email.strip().lower()
    existing = db.query(models.User).filter(models.User.email == clean_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    clean_blood_group = user_in.blood_group.strip().upper() if user_in.blood_group else "O+"
    pwd_hash = hash_password(user_in.password)

    new_user = models.User(
        name=user_in.name.strip(),
        email=clean_email,
        phone=user_in.phone.strip(),
        password_hash=pwd_hash,
        blood_group=clean_blood_group,
        location=user_in.location.strip() if user_in.location else "Coimbatore",
        latitude=user_in.latitude or 11.0168,
        longitude=user_in.longitude or 76.9558,
        availability=(user_in.availability or "AVAILABLE").upper(),
        donation_type=user_in.donation_type or "whole_blood"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Synchronize corresponding Donor profile so Phase 1-5 tests & matching find this user
    linked_donor = models.Donor(
        name=new_user.name,
        phone=new_user.phone,
        blood_group=new_user.blood_group,
        city=new_user.location,
        latitude=new_user.latitude,
        longitude=new_user.longitude,
        availability=new_user.availability,
        is_verified=True,
        donation_type=new_user.donation_type,
        user_id=new_user.id
    )
    db.add(linked_donor)
    db.commit()

    # Welcome notification
    welcome_notif = models.Notification(
        user_id=new_user.id,
        type="SYSTEM",
        title="Welcome to Life-Link",
        message=f"Welcome, {new_user.name}! Your account is active. You can request blood for yourself or family, or respond as a voluntary donor."
    )
    db.add(welcome_notif)
    db.commit()

    # Calculate review date for response
    reminder = matching.calculate_eligibility_reminder(new_user.last_donation_date, new_user.donation_type)
    new_user.next_review_date = reminder["next_review_date"]
    new_user.eligibility_status_message = reminder["status_message"]

    return new_user


@app.post("/auth/login", response_model=schemas.UserResponse)
def login_user(login_in: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates a user using secure password hash comparison.
    """
    clean_email = login_in.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == clean_email).first()
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    reminder = matching.calculate_eligibility_reminder(user.last_donation_date, user.donation_type)
    user.next_review_date = reminder["next_review_date"]
    user.eligibility_status_message = reminder["status_message"]
    return user


@app.get("/users", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    """
    List all users (convenient for switching user profiles in demo/testing).
    """
    users = db.query(models.User).order_by(models.User.id.asc()).all()
    for u in users:
        reminder = matching.calculate_eligibility_reminder(u.last_donation_date, u.donation_type)
        u.next_review_date = reminder["next_review_date"]
        u.eligibility_status_message = reminder["status_message"]
    return users


@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    """
    Retrieves user profile and computes current eligibility reminder.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    reminder = matching.calculate_eligibility_reminder(user.last_donation_date, user.donation_type)
    user.next_review_date = reminder["next_review_date"]
    user.eligibility_status_message = reminder["status_message"]
    return user


@app.put("/users/{user_id}/profile", response_model=schemas.UserResponse)
def update_user_profile(user_id: int, updates: schemas.UserProfileUpdate, db: Session = Depends(get_db)):
    """
    Updates profile details (name, phone, blood group, location).
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User #{user_id} not found")

    if updates.name is not None:
        user.name = updates.name.strip()
    if updates.phone is not None:
        user.phone = updates.phone.strip()
    if updates.blood_group is not None:
        user.blood_group = updates.blood_group.strip().upper()
    if updates.location is not None:
        user.location = updates.location.strip()
    if updates.latitude is not None:
        user.latitude = updates.latitude
    if updates.longitude is not None:
        user.longitude = updates.longitude
    if updates.availability is not None:
        user.availability = updates.availability.strip().upper()
    if updates.donation_type is not None:
        user.donation_type = updates.donation_type.strip().lower()

    # Sync linked donor record
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if donor:
        donor.name = user.name
        donor.phone = user.phone
        donor.blood_group = user.blood_group
        donor.city = user.location
        donor.latitude = user.latitude
        donor.longitude = user.longitude
        donor.availability = user.availability
        donor.donation_type = user.donation_type

    db.commit()
    db.refresh(user)

    reminder = matching.calculate_eligibility_reminder(user.last_donation_date, user.donation_type)
    user.next_review_date = reminder["next_review_date"]
    user.eligibility_status_message = reminder["status_message"]
    return user


@app.patch("/users/{user_id}/availability", response_model=schemas.UserResponse)
def update_user_availability(user_id: int, avail: schemas.UserAvailabilityUpdate, db: Session = Depends(get_db)):
    """
    Toggles user's donation availability (AVAILABLE, UNAVAILABLE, REVIEW_NEEDED).
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User #{user_id} not found")

    new_val = avail.availability.strip().upper()
    if new_val not in ["AVAILABLE", "UNAVAILABLE", "REVIEW_NEEDED"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid availability status.")

    user.availability = new_val

    # Sync linked donor record
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if donor:
        donor.availability = new_val

    db.commit()
    db.refresh(user)

    reminder = matching.calculate_eligibility_reminder(user.last_donation_date, user.donation_type)
    user.next_review_date = reminder["next_review_date"]
    user.eligibility_status_message = reminder["status_message"]
    return user


@app.get("/users/{user_id}/emergency-requests", response_model=List[schemas.EmergencyRequestResponse])
def get_user_emergencies(user_id: int, db: Session = Depends(get_db)):
    """
    Lists all emergency requests requested by this user account.
    """
    return db.query(models.EmergencyRequest).filter(models.EmergencyRequest.user_id == user_id).order_by(models.EmergencyRequest.id.desc()).all()


@app.get("/users/{user_id}/donor-responses", response_model=List[schemas.DonorResponseDetail])
def get_user_donor_responses(user_id: int, db: Session = Depends(get_db)):
    """
    Lists all responses this user has made to emergency calls.
    """
    return db.query(models.DonorResponse).filter(models.DonorResponse.user_id == user_id).order_by(models.DonorResponse.id.desc()).all()


@app.get("/users/{user_id}/notifications", response_model=List[schemas.NotificationResponse])
def get_user_notifications(user_id: int, db: Session = Depends(get_db)):
    """
    Retrieves all verified notifications for this user, sorted newest first.
    """
    return db.query(models.Notification).filter(models.Notification.user_id == user_id).order_by(models.Notification.id.desc()).all()


@app.patch("/users/{user_id}/notifications/{notif_id}/read", response_model=schemas.NotificationResponse)
def mark_notification_read(user_id: int, notif_id: int, db: Session = Depends(get_db)):
    """
    Marks a single notification as read.
    """
    notif = db.query(models.Notification).filter(
        models.Notification.id == notif_id,
        models.Notification.user_id == user_id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@app.post("/users/{user_id}/notifications/read-all")
def mark_all_notifications_read(user_id: int, db: Session = Depends(get_db)):
    """
    Marks all notifications for this user as read.
    """
    db.query(models.Notification).filter(models.Notification.user_id == user_id).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read."}


@app.get("/users/{user_id}/donations", response_model=List[schemas.DonationResponse])
def get_user_donations(user_id: int, db: Session = Depends(get_db)):
    """
    Retrieves verified donation history for this user.
    """
    return db.query(models.Donation).filter(models.Donation.user_id == user_id).order_by(models.Donation.id.desc()).all()


# ==========================================
# 2. MATCHED BLOOD REQUEST FEED (BLOOD REQUESTS I CAN HELP WITH)
# ==========================================

@app.get("/users/{user_id}/matched-requests", response_model=List[schemas.MatchedEmergencyFeedItem])
def get_matched_requests_feed(user_id: int, db: Session = Depends(get_db)):
    """
    Requirement 8: 'Blood Requests You Can Help With'
    Only shows relevant active requests that the current user can help with
    according to biological blood compatibility, current donor availability, and distance.
    Provides second voluntary discovery path.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User #{user_id} not found")

    feed = matching.find_matched_emergencies_for_user(db=db, user=user)
    return feed


# ==========================================
# 3. INTERACTIVE MULTILINGUAL AI BOT ENDPOINTS
# ==========================================

@app.post("/ai/chat", response_model=schemas.AIChatResponse)
def ai_chat_interaction(payload: schemas.AIChatMessage, db: Session = Depends(get_db)):
    """
    Requirement 2, 3, 4, 11:
    Interactive Multilingual AI Assistant (English, Tamil, Tanglish).
    - Natural language understanding (patient name vs account holder, blood group, units, hospital, urgency).
    - Asks for missing information instead of inventing.
    - Does NOT hallucinate system status. Queries real database for verified states.
    - Generates editable confirmation card BEFORE creating emergency.
    - Communicates actual cascade events and donor counts.
    """
    message = payload.message.strip()
    user_id = payload.user_id
    requester_name = payload.requester_name

    # Check if user is asking about an existing emergency status
    status_query_match = re.search(r'\b(?:status|track|cascade|update|emergency|request)\s*#?(\d+)\b', message, re.IGNORECASE)
    emergency_id = payload.active_emergency_id
    if status_query_match:
        emergency_id = int(status_query_match.group(1))

    if emergency_id and any(term in message.lower() for term in ["status", "how many", "donor", "cascade", "round", "accepted", "update", "track"]):
        req = db.query(models.EmergencyRequest).filter(models.EmergencyRequest.id == emergency_id).first()
        if not req:
            return {
                "reply": f"I checked the database, but could not find Emergency #{emergency_id}.",
                "ready_for_confirmation": False,
                "extracted_fields": {
                    "resource_type": "blood", "component": "whole_blood", "blood_group": None,
                    "units_required": None, "hospital_name": None, "urgency": "NORMAL",
                    "contact_phone": None, "patient_name": "Emergency Patient", "requester_name": requester_name
                },
                "missing_fields": [],
                "confirmation_card": None,
                "backend_status": None
            }

        # Query matching engine & responses to get verified database facts
        matches_result = matching.find_matches_for_request(db=db, emergency_request=req)
        total_compatible = matches_result["total_compatible_found"]
        accepted_responses = db.query(models.DonorResponse).filter(
            models.DonorResponse.emergency_request_id == req.id,
            models.DonorResponse.action == "ACCEPT"
        ).count()

        # Database is source of truth: 5 distinct verified states
        if req.status == "DONATION_COMPLETED" or req.donation_completed:
            state_text = f"Donation has been verified and completed at {req.hospital_name}! Thank you to all donors."
        elif req.status == "HOSPITAL_CONFIRMED" or req.hospital_confirmed:
            state_text = f"Hospital {req.hospital_name} has confirmed the emergency requirement. Clinical screening is in progress."
        elif accepted_responses > 0:
            state_text = f"{accepted_responses} donor(s) have accepted and indicated willingness to help. Awaiting hospital coordination."
        elif total_compatible > 0:
            state_text = f"I found {total_compatible} compatible available donor(s) in Round {req.current_cascade_round}. Notifications have been sent and we are waiting for donor responses."
        else:
            state_text = f"No compatible available donors have been found in the current radius. Blood bank escalation is recommended."

        backend_status_payload = {
            "emergency_id": req.id,
            "status": req.status,
            "hospital_name": req.hospital_name,
            "blood_group": req.blood_group,
            "units_needed": req.units_needed,
            "units_accepted": req.units_accepted,
            "cascade_round": req.current_cascade_round,
            "total_compatible_found": total_compatible,
            "accepted_responses_count": accepted_responses,
            "hospital_confirmed": req.hospital_confirmed,
            "screening_status": req.screening_status,
            "donation_completed": req.donation_completed
        }

        return {
            "reply": f"Emergency #{req.id} Status Report ({req.hospital_name}): {state_text}",
            "ready_for_confirmation": False,
            "extracted_fields": {
                "resource_type": req.resource_type, "component": req.component, "blood_group": req.blood_group,
                "units_required": req.units_needed, "hospital_name": req.hospital_name, "urgency": req.urgency,
                "contact_phone": req.contact_phone, "patient_name": req.patient_name, "requester_name": req.requester_name
            },
            "missing_fields": [],
            "confirmation_card": None,
            "backend_status": backend_status_payload
        }

    # Otherwise, parse emergency request parameters
    parse_result = ai_parser.parse_emergency_message(
        message=message,
        existing_fields=payload.accumulated_fields,
        requester_name=requester_name
    )

    parsed = parse_result["parsed_request"]
    missing = parse_result["missing_fields"]
    ready = parse_result["success"]

    conf_card = None
    if ready:
        conf_card = ai_parser.format_confirmation_card(parsed)
        reply = (
            f"I have understood your emergency request for {parsed['patient_name']}: "
            f"{parsed['units_required']} unit(s) of {parsed['blood_group']} blood at {parsed['hospital_name']} ({parsed['urgency']}). "
            "Please review the confirmation card below and click 'Confirm Emergency' to initiate matching."
        )
    else:
        reply = parse_result["message"]

    return {
        "reply": reply,
        "ready_for_confirmation": ready,
        "extracted_fields": parsed,
        "missing_fields": missing,
        "confirmation_card": conf_card,
        "backend_status": None
    }


@app.post("/ai/confirm-emergency", response_model=schemas.EmergencyRequestResponse, status_code=status.HTTP_201_CREATED)
def confirm_emergency_from_bot(payload: schemas.EmergencyRequestCreate, db: Session = Depends(get_db)):
    """
    Requirement 3 & 6:
    Only after the user reviews and confirms the card:
    Creates the EmergencyRequest in the database, runs intelligent matching,
    and NOTIFIES ALL RELEVANT COMPATIBLE AND AVAILABLE DONORS.
    """
    clean_blood_group = payload.blood_group.strip().upper()

    hosp_upper = payload.hospital_name.strip().upper()
    coords = HOSPITAL_COORDINATES.get(hosp_upper, (payload.latitude or 11.0267, payload.longitude or 77.0348))

    db_emergency = models.EmergencyRequest(
        user_id=payload.user_id,
        requester_name=payload.requester_name or "Account Holder",
        patient_name=payload.patient_name.strip() if payload.patient_name else "Emergency Patient",
        hospital_name=payload.hospital_name.strip(),
        hospital_city=payload.hospital_city.strip() if payload.hospital_city else "Coimbatore",
        latitude=coords[0],
        longitude=coords[1],
        resource_type=payload.resource_type.strip().lower() if payload.resource_type else "blood",
        component=payload.component.strip().lower() if payload.component else "whole_blood",
        blood_group=clean_blood_group,
        units_needed=payload.units_needed,
        units_accepted=0,
        urgency=(payload.urgency or "CRITICAL").upper(),
        contact_phone=payload.contact_phone.strip(),
        status="SEARCHING",
        current_cascade_round=1,
        notes=payload.notes or f"Emergency request for {payload.patient_name} at {payload.hospital_name}"
    )
    db.add(db_emergency)
    db.commit()
    db.refresh(db_emergency)

    # Immediately execute matching to find all relevant compatible available donors
    matches_data = matching.find_matches_for_request(db=db, emergency_request=db_emergency)
    
    # Requirement 6: NOTIFY ALL RELEVANT COMPATIBLE AVAILABLE DONORS
    if matches_data["matches"]:
        notifications_service.notify_compatible_available_donors(
            db=db,
            emergency_request=db_emergency,
            matched_donors=matches_data["matches"],
            round_num=1
        )
        db_emergency.status = "COMPATIBLE_DONORS_FOUND"
    else:
        db_emergency.status = "NO_COMPATIBLE_DONORS"

    db.commit()
    db.refresh(db_emergency)
    return db_emergency


# ==========================================
# 4. PRESERVED PHASE 1 DONOR ENDPOINTS
# ==========================================

@app.post("/donors", response_model=schemas.DonorResponse, status_code=status.HTTP_201_CREATED)
def create_donor(donor: schemas.DonorCreate, db: Session = Depends(get_db)):
    """
    Register a new voluntary blood donor (Phase 1 legacy compatibility).
    """
    clean_blood_group = donor.blood_group.strip().upper()

    db_donor = models.Donor(
        name=donor.name.strip(),
        phone=donor.phone.strip(),
        blood_group=clean_blood_group,
        city=donor.city.strip() if donor.city else "Coimbatore",
        latitude=donor.latitude or 11.0168,
        longitude=donor.longitude or 76.9558,
        availability=(donor.availability or "AVAILABLE").upper(),
        is_verified=True,
        last_donation_date=donor.last_donation_date,
        donation_type=donor.donation_type or "whole_blood"
    )
    db.add(db_donor)
    db.commit()
    db.refresh(db_donor)
    return db_donor


@app.get("/donors", response_model=List[schemas.DonorResponse])
def get_donors(
    blood_group: Optional[str] = None,
    availability: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve list of donors, with optional filtering by blood group and availability.
    """
    query = db.query(models.Donor)
    if blood_group:
        normalized_group = blood_group.strip().replace(" ", "+").upper()
        query = query.filter(models.Donor.blood_group == normalized_group)
    if availability:
        query = query.filter(models.Donor.availability == availability.strip().upper())
    
    return query.order_by(models.Donor.id.desc()).all()


@app.get("/donors/{donor_id}", response_model=schemas.DonorResponse)
def get_donor(donor_id: int, db: Session = Depends(get_db)):
    """
    Retrieve details of a single donor by ID.
    """
    donor = db.query(models.Donor).filter(models.Donor.id == donor_id).first()
    if not donor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Donor with ID {donor_id} not found"
        )
    return donor


@app.patch("/donors/{donor_id}/availability", response_model=schemas.DonorResponse)
def update_donor_availability(
    donor_id: int,
    update_data: schemas.DonorAvailabilityUpdate,
    db: Session = Depends(get_db)
):
    """
    Toggles a donor's availability (AVAILABLE, MAYBE_AVAILABLE, UNAVAILABLE).
    """
    donor = db.query(models.Donor).filter(models.Donor.id == donor_id).first()
    if not donor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Donor with ID {donor_id} not found"
        )

    new_status = update_data.availability.strip().upper()
    if new_status not in ["AVAILABLE", "MAYBE_AVAILABLE", "UNAVAILABLE"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Availability status must be 'AVAILABLE', 'MAYBE_AVAILABLE', or 'UNAVAILABLE'"
        )

    donor.availability = new_status
    if donor.user_id:
        user = db.query(models.User).filter(models.User.id == donor.user_id).first()
        if user:
            user.availability = new_status

    db.commit()
    db.refresh(donor)
    return donor


# ==========================================
# 5. PRESERVED EMERGENCY REQUEST ENDPOINTS
# ==========================================

@app.post("/emergency-requests", response_model=schemas.EmergencyRequestResponse, status_code=status.HTTP_201_CREATED)
def create_emergency_request(
    request: schemas.EmergencyRequestCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new emergency blood or component request (Phase 1 legacy compatibility).
    """
    clean_blood_group = request.blood_group.strip().upper()

    db_request = models.EmergencyRequest(
        user_id=request.user_id,
        requester_name=request.requester_name or "Emergency Requester",
        patient_name=request.patient_name.strip() if request.patient_name else "Emergency Patient",
        hospital_name=request.hospital_name.strip(),
        hospital_city=request.hospital_city.strip() if request.hospital_city else "Coimbatore",
        latitude=request.latitude or 11.0267,
        longitude=request.longitude or 77.0348,
        resource_type=request.resource_type.strip().lower() if request.resource_type else "blood",
        component=request.component.strip().lower() if request.component else "whole_blood",
        blood_group=clean_blood_group,
        units_needed=request.units_needed,
        units_accepted=0,
        urgency=(request.urgency or "CRITICAL").upper(),
        contact_phone=request.contact_phone.strip(),
        status="SEARCHING",
        current_cascade_round=1,
        notes=request.notes
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    # Automatically notify compatible available donors
    matches_data = matching.find_matches_for_request(db=db, emergency_request=db_request)
    if matches_data["matches"]:
        notifications_service.notify_compatible_available_donors(
            db=db,
            emergency_request=db_request,
            matched_donors=matches_data["matches"],
            round_num=1
        )

    return db_request


@app.get("/emergency-requests", response_model=List[schemas.EmergencyRequestResponse])
def get_emergency_requests(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve all emergency requests, optionally filtered by status.
    """
    query = db.query(models.EmergencyRequest)
    if status_filter:
        query = query.filter(models.EmergencyRequest.status == status_filter.upper())
    return query.order_by(models.EmergencyRequest.id.desc()).all()


@app.get("/emergency-requests/{request_id}", response_model=schemas.EmergencyRequestResponse)
def get_emergency_request(request_id: int, db: Session = Depends(get_db)):
    """
    Retrieve details of an emergency request by ID.
    """
    req = db.query(models.EmergencyRequest).filter(models.EmergencyRequest.id == request_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency request with ID {request_id} not found"
        )
    return req


# ==========================================
# 6. PRESERVED PHASE 2: MATCHING ENDPOINT
# ==========================================

@app.get("/emergency-requests/{request_id}/matches", response_model=schemas.EmergencyMatchesResponse)
def get_matches_for_emergency(
    request_id: int,
    max_distance_km: Optional[float] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Intelligently finds and ranks compatible, available blood donors for an emergency request.
    Calculates proximity using Haversine distance from the hospital.
    """
    req = db.query(models.EmergencyRequest).filter(models.EmergencyRequest.id == request_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency request with ID {request_id} not found"
        )

    match_result = matching.find_matches_for_request(
        db=db,
        emergency_request=req,
        max_distance_km=max_distance_km,
        limit=limit
    )
    return match_result


# ==========================================
# 7. PRESERVED PHASE 3: ADAPTIVE CASCADE ENDPOINT
# ==========================================

@app.get("/emergency-requests/{request_id}/cascade", response_model=schemas.CascadeResponse)
def get_emergency_cascade(
    request_id: int,
    db: Session = Depends(get_db)
):
    """
    Executes progressive adaptive cascade (Round 1: 0-5km, Round 2: 5-15km, Round 3: 15-25km).
    Expands search radius until required units are met or blood-bank fallback is needed.
    """
    req = db.query(models.EmergencyRequest).filter(models.EmergencyRequest.id == request_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency request with ID {request_id} not found"
        )

    cascade_result = cascade.execute_emergency_cascade(db=db, emergency_request=req)
    return cascade_result


# ==========================================
# 8. PRESERVED PHASE 4: AI PARSER ENDPOINTS
# ==========================================

HOSPITAL_COORDINATES = {
    "KMCH": (11.0267, 77.0348),
    "PSG": (11.0245, 77.0034),
    "PSG HOSPITALS": (11.0245, 77.0034),
    "PSG HOSPITAL": (11.0245, 77.0034),
    "GKNM": (11.0112, 76.9814),
    "GKNM HOSPITAL": (11.0112, 76.9814),
    "CMCH": (10.9995, 76.9634),
    "COIMBATORE MEDICAL COLLEGE HOSPITAL": (10.9995, 76.9634),
    "GANGA": (11.0195, 76.9535),
    "GANGA HOSPITAL": (11.0195, 76.9535),
    "APOLLO": (13.0827, 80.2707),
    "APOLLO HOSPITALS": (13.0827, 80.2707),
    "ROYAL CARE": (11.0425, 77.0512),
    "ROYAL CARE HOSPITAL": (11.0425, 77.0512)
}


@app.post("/ai/parse-request", response_model=schemas.AIParseResponse)
def parse_emergency_ai(
    payload: schemas.AIParseRequest,
    db: Session = Depends(get_db)
):
    """
    Multilingual AI parser (English, Tanglish, Tamil).
    Converts unstructured voice/text input into structured emergency fields.
    Does not invent missing fields.
    If auto_create=True and all fields are present, creates a normal EmergencyRequest.
    """
    parse_result = ai_parser.parse_emergency_message(payload.message, requester_name=payload.requester_name)
    
    created_id = None
    created_obj = None

    if parse_result["success"] and payload.auto_create:
        parsed_data = parse_result["parsed_request"]
        hosp_upper = (parsed_data["hospital_name"] or "").strip().upper()
        coords = HOSPITAL_COORDINATES.get(hosp_upper, (11.0267, 77.0348))

        contact = (
            parsed_data.get("contact_phone") 
            or payload.contact_phone 
            or "+91 94433 00000"
        )

        db_emergency = models.EmergencyRequest(
            user_id=payload.user_id,
            requester_name=payload.requester_name or "Emergency Requester",
            patient_name=parsed_data.get("patient_name") or "Emergency Patient (AI Bot)",
            hospital_name=parsed_data["hospital_name"],
            hospital_city="Coimbatore",
            latitude=coords[0],
            longitude=coords[1],
            resource_type=parsed_data["resource_type"],
            component=parsed_data["component"],
            blood_group=parsed_data["blood_group"],
            units_needed=parsed_data["units_required"],
            units_accepted=0,
            urgency=parsed_data["urgency"],
            contact_phone=contact,
            status="SEARCHING",
            current_cascade_round=1,
            notes=f"AI voice/text request: \"{payload.message}\""
        )
        db.add(db_emergency)
        db.commit()
        db.refresh(db_emergency)

        created_id = db_emergency.id
        created_obj = db_emergency
        parse_result["message"] += f" Emergency Request #{created_id} created in system!"

    return {
        "success": parse_result["success"],
        "parsed_request": parse_result["parsed_request"],
        "missing_fields": parse_result["missing_fields"],
        "message": parse_result["message"],
        "created_emergency_request_id": created_id,
        "emergency_request": created_obj
    }


@app.post("/ai/create-emergency-from-text", response_model=schemas.EmergencyRequestResponse, status_code=status.HTTP_201_CREATED)
def create_emergency_from_text(
    payload: schemas.AIParseRequest,
    db: Session = Depends(get_db)
):
    """
    End-to-End Pipeline:
    Text -> AI Parser -> Creates standard Phase 1 EmergencyRequest.
    Raises 400 if required emergency fields are missing.
    """
    parse_result = ai_parser.parse_emergency_message(payload.message, requester_name=payload.requester_name)
    if not parse_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": parse_result["message"],
                "missing_fields": parse_result["missing_fields"]
            }
        )

    parsed_data = parse_result["parsed_request"]
    hosp_upper = (parsed_data["hospital_name"] or "").strip().upper()
    coords = HOSPITAL_COORDINATES.get(hosp_upper, (11.0267, 77.0348))

    contact = (
        parsed_data.get("contact_phone") 
        or payload.contact_phone 
        or "+91 94433 00000"
    )

    db_emergency = models.EmergencyRequest(
        user_id=payload.user_id,
        requester_name=payload.requester_name or "Emergency Requester",
        patient_name=parsed_data.get("patient_name") or "Emergency Patient (AI Bot)",
        hospital_name=parsed_data["hospital_name"],
        hospital_city="Coimbatore",
        latitude=coords[0],
        longitude=coords[1],
        resource_type=parsed_data["resource_type"],
        component=parsed_data["component"],
        blood_group=parsed_data["blood_group"],
        units_needed=parsed_data["units_required"],
        units_accepted=0,
        urgency=parsed_data["urgency"],
        contact_phone=contact,
        status="SEARCHING",
        current_cascade_round=1,
        notes=f"AI voice/text request: \"{payload.message}\""
    )
    db.add(db_emergency)
    db.commit()
    db.refresh(db_emergency)
    return db_emergency


# ==========================================
# 9. DONOR RESPONSE & LIFECYCLE MANAGEMENT
# ==========================================

@app.post("/emergency-requests/{request_id}/respond", response_model=schemas.DonorResponseResult)
def respond_to_emergency(
    request_id: int,
    action_data: schemas.DonorResponseAction,
    db: Session = Depends(get_db)
):
    """
    Requirement 6 & 7:
    Allows a matched donor / user to ACCEPT or DECLINE an emergency request.
    Registers willing intent (STATE 1: DONOR WILLING / ACCEPTED).
    Does NOT mark hospital confirmed or donation completed.
    """
    req = db.query(models.EmergencyRequest).filter(models.EmergencyRequest.id == request_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency request with ID {request_id} not found"
        )

    # Resolve donor or user identity
    donor_id = action_data.donor_id
    user_id = action_data.user_id
    donor_name = "Voluntary Donor"
    blood_group = "O+"

    if donor_id:
        donor = db.query(models.Donor).filter(models.Donor.id == donor_id).first()
        if not donor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Donor with ID {donor_id} not found"
            )
        donor_name = donor.name
        blood_group = donor.blood_group
        if not user_id and donor.user_id:
            user_id = donor.user_id
    elif user_id:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        donor_name = user.name
        blood_group = user.blood_group
        # Link donor id if available
        d = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
        if d:
            donor_id = d.id
    else:
        raise HTTPException(status_code=400, detail="Must provide donor_id or user_id.")

    clean_action = action_data.action.strip().upper()

    # Record or update DonorResponse
    existing_resp = db.query(models.DonorResponse).filter(
        models.DonorResponse.emergency_request_id == req.id,
        (models.DonorResponse.donor_id == donor_id) if donor_id else (models.DonorResponse.user_id == user_id)
    ).first()

    if not existing_resp:
        existing_resp = models.DonorResponse(
            emergency_request_id=req.id,
            user_id=user_id,
            donor_id=donor_id,
            donor_name=donor_name,
            blood_group=blood_group,
            action=clean_action,
            status="WILLING" if clean_action == "ACCEPT" else "DECLINED"
        )
        db.add(existing_resp)
    else:
        existing_resp.action = clean_action
        existing_resp.status = "WILLING" if clean_action == "ACCEPT" else "DECLINED"

    if clean_action == "ACCEPT":
        req.units_accepted += 1
        if req.units_accepted >= req.units_needed:
            req.status = "TARGET_REACHED"
        else:
            req.status = "DONOR_ACCEPTED"
        message = f"Thank you, {donor_name}! Your willingness to help has been registered. The hospital has been notified to verify and schedule."
    else:
        clean_action = "DECLINE"
        message = f"Thank you for letting us know, {donor_name}. The request has been declined."

    db.commit()
    db.refresh(req)

    return {
        "emergency_request_id": req.id,
        "donor_id": donor_id or 0,
        "user_id": user_id,
        "action": clean_action,
        "units_needed": req.units_needed,
        "units_accepted": req.units_accepted,
        "status": req.status,
        "message": message
    }


# ==========================================
# 10. HOSPITAL WORKFLOW (STATE 2 & 3: CONFIRMATION, SCREENING, DONATION)
# ==========================================

@app.post("/emergency-requests/{request_id}/hospital-confirm")
def hospital_confirm_emergency(
    request_id: int,
    payload: Optional[schemas.HospitalConfirmRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Requirement 7: STATE 2: HOSPITAL CONFIRMED
    Hospital verifies blood requirement and schedules donor appointment.
    """
    req = db.query(models.EmergencyRequest).filter(models.EmergencyRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Emergency request not found")

    req.hospital_confirmed = True
    req.status = "HOSPITAL_CONFIRMED"
    db.commit()

    # Distribute verified notification
    notifications_service.notify_hospital_confirmation(
        db=db,
        emergency_request=req,
        hospital_message=f"{req.hospital_name} has verified the requirement for {req.patient_name} ({req.blood_group}). Clinical screening scheduled."
    )

    return {
        "emergency_request_id": req.id,
        "status": req.status,
        "hospital_confirmed": True,
        "message": f"Hospital confirmation recorded for Emergency #{req.id}. Donors and requester notified."
    }


@app.post("/emergency-requests/{request_id}/screening-update")
def hospital_screening_update(
    request_id: int,
    payload: schemas.ScreeningUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Requirement 7 & 24: SCREENING UPDATE
    Medical screening passed / failed at hospital blood bank.
    """
    req = db.query(models.EmergencyRequest).filter(models.EmergencyRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Emergency request not found")

    donor_user_id = payload.donor_user_id
    passed = payload.passed

    req.screening_status = "PASSED" if passed else "FAILED"
    if passed:
        req.status = "SCREENING_COMPLETED"
    else:
        req.status = "SCREENING_PENDING"
    db.commit()

    notifications_service.notify_screening_update(
        db=db,
        emergency_request=req,
        donor_user_id=donor_user_id,
        passed=passed
    )

    return {
        "emergency_request_id": req.id,
        "screening_status": req.screening_status,
        "status": req.status,
        "message": f"Clinical screening result ({req.screening_status}) recorded."
    }


@app.post("/emergency-requests/{request_id}/complete-donation")
def hospital_complete_donation(
    request_id: int,
    payload: schemas.CompleteDonationRequest,
    db: Session = Depends(get_db)
):
    """
    Requirement 7 & 9: STATE 3: DONATION COMPLETED
    Recorded ONLY after the actual hospital/blood-bank donation process.
    Updates:
    - Emergency status to DONATION_COMPLETED
    - User's donation history & last_donation_date
    - User's availability state & next review date
    - Verified notification record
    """
    req = db.query(models.EmergencyRequest).filter(models.EmergencyRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Emergency request not found")

    donor_user_id = payload.donor_user_id
    units_donated = payload.units_donated if payload.units_donated is not None else (payload.units or 1)
    notes = payload.notes

    user = db.query(models.User).filter(models.User.id == donor_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Donor user #{donor_user_id} not found")

    # 1. Update emergency request
    req.donation_completed = True
    req.status = "DONATION_COMPLETED"

    # 2. Record Donation in history
    donation = models.Donation(
        user_id=user.id,
        emergency_request_id=req.id,
        hospital_name=req.hospital_name,
        blood_group=req.blood_group,
        component=req.component or "whole_blood",
        units=units_donated,
        donation_date=date.today(),
        status="COMPLETED",
        notes=notes or f"Donation fulfilled for Emergency #{req.id}"
    )
    db.add(donation)

    # 3. Update User & Donor cooldown & availability
    user.last_donation_date = date.today()
    user.availability = "REVIEW_NEEDED"

    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if donor:
        donor.last_donation_date = date.today()
        donor.availability = "REVIEW_NEEDED"

    # 4. Notify donor
    notifications_service.notify_donation_completion(
        db=db,
        user_id=user.id,
        emergency_request_id=req.id,
        hospital_name=req.hospital_name,
        blood_group=req.blood_group,
        units=units_donated
    )

    db.commit()

    return {
        "emergency_request_id": req.id,
        "donation_id": donation.id,
        "donor_user_id": user.id,
        "status": "DONATION_COMPLETED",
        "message": f"Donation verified and completed! Recorded in {user.name}'s history."
    }


# ==========================================
# 11. DEMO DATA SEEDING HELPER
# ==========================================

@app.post("/seed-demo-data")
def seed_demo_data(force: bool = False, db: Session = Depends(get_db)):
    """
    Seeds realistic sample users, donors, notifications, and active emergencies
    demonstrating the unified single normal user account architecture.
    """
    if force:
        db.query(models.Notification).delete()
        db.query(models.Donation).delete()
        db.query(models.DonorResponse).delete()
        db.query(models.EmergencyRequest).delete()
        db.query(models.Donor).delete()
        db.query(models.User).delete()
        db.commit()
    else:
        existing_users = db.query(models.User).count()
        if existing_users > 0:
            return {
                "message": f"Database already contains {existing_users} users. Skipping seed.",
                "total_users": existing_users
            }

    pwd_hash = hash_password("password123")

    # Sample Users (demonstrating normal user account handling both requesting & donating)
    users_data = [
        # User 1: Akalya (Requester for father Sathya, also eligible donor)
        models.User(
            name="Akalya M",
            email="akalya@example.com",
            phone="+91 94433 12345",
            password_hash=pwd_hash,
            blood_group="O+",
            location="Coimbatore (KMCH Area)",
            latitude=11.0310,
            longitude=77.0320,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=150),
            donation_type="whole_blood"
        ),
        # User 2: Sathya N (Family member / patient profile)
        models.User(
            name="Sathya N",
            email="sathya@example.com",
            phone="+91 94433 22222",
            password_hash=pwd_hash,
            blood_group="O+",
            location="Coimbatore (Peelamedu)",
            latitude=11.0280,
            longitude=77.0120,
            availability="UNAVAILABLE",
            last_donation_date=None,
            donation_type="whole_blood"
        ),
        # User 3: Arun Kumar (Near KMCH ~1.2 km)
        models.User(
            name="Arun Kumar",
            email="arun@example.com",
            phone="+91 98421 11001",
            password_hash=pwd_hash,
            blood_group="O+",
            location="Coimbatore (KMCH Area)",
            latitude=11.0350,
            longitude=77.0310,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=120),
            donation_type="whole_blood"
        ),
        # User 4: Priya Senthil (~2.5 km)
        models.User(
            name="Priya Senthil",
            email="priya@example.com",
            phone="+91 98421 11002",
            password_hash=pwd_hash,
            blood_group="O+",
            location="Coimbatore (Peelamedu)",
            latitude=11.0280,
            longitude=77.0120,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=100),
            donation_type="whole_blood"
        ),
        # User 5: Karthik R (Universal O- donor ~1.9 km)
        models.User(
            name="Karthik R",
            email="karthik@example.com",
            phone="+91 98421 11003",
            password_hash=pwd_hash,
            blood_group="O-",
            location="Coimbatore (Hopes College)",
            latitude=11.0240,
            longitude=77.0180,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=150),
            donation_type="whole_blood"
        ),
        # User 6: Divya M (A+ donor)
        models.User(
            name="Divya M",
            email="divya@example.com",
            phone="+91 98421 11004",
            password_hash=pwd_hash,
            blood_group="A+",
            location="Coimbatore (Sitra)",
            latitude=11.0390,
            longitude=77.0420,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=95),
            donation_type="whole_blood"
        ),
        # User 7: Suresh Balaji (Round 2: Gandhipuram ~7.4 km)
        models.User(
            name="Suresh Balaji",
            email="suresh@example.com",
            phone="+91 98421 11005",
            password_hash=pwd_hash,
            blood_group="O+",
            location="Coimbatore (Gandhipuram)",
            latitude=11.0183,
            longitude=76.9669,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=110),
            donation_type="whole_blood"
        ),
        # User 8: Ananya Lakshmi (Round 2: RS Puram ~10.1 km)
        models.User(
            name="Ananya Lakshmi",
            email="ananya@example.com",
            phone="+91 98421 11006",
            password_hash=pwd_hash,
            blood_group="O+",
            location="Coimbatore (RS Puram)",
            latitude=11.0080,
            longitude=76.9450,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=130),
            donation_type="whole_blood"
        ),
        # User 9: Vignesh K (B+ donor, Saibaba Colony ~10.2 km)
        models.User(
            name="Vignesh K",
            email="vignesh@example.com",
            phone="+91 98421 11007",
            password_hash=pwd_hash,
            blood_group="B+",
            location="Coimbatore (Saibaba Colony)",
            latitude=11.0290,
            longitude=76.9420,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=140),
            donation_type="whole_blood"
        ),
        # User 10: Deepak Natarajan (Round 3: Sulur ~16.5 km)
        models.User(
            name="Deepak Natarajan",
            email="deepak@example.com",
            phone="+91 98421 11008",
            password_hash=pwd_hash,
            blood_group="O+",
            location="Coimbatore Outskirts (Sulur)",
            latitude=11.0270,
            longitude=77.1260,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=180),
            donation_type="whole_blood"
        ),
        # User 11: Manoj C (Ineligible: recently donated 20 days ago)
        models.User(
            name="Manoj C",
            email="manoj@example.com",
            phone="+91 98421 11009",
            password_hash=pwd_hash,
            blood_group="O+",
            location="Coimbatore (Peelamedu)",
            latitude=11.0290,
            longitude=77.0150,
            availability="AVAILABLE",
            last_donation_date=date.today() - timedelta(days=20),
            donation_type="whole_blood"
        ),
        # User 12: Rahul V (Unavailable donor)
        models.User(
            name="Rahul V",
            email="rahul@example.com",
            phone="+91 98421 11010",
            password_hash=pwd_hash,
            blood_group="O+",
            location="Coimbatore (Singanallur)",
            latitude=11.0010,
            longitude=77.0210,
            availability="UNAVAILABLE",
            last_donation_date=date.today() - timedelta(days=150),
            donation_type="whole_blood"
        )
    ]
    db.add_all(users_data)
    db.commit()

    # Synchronize Donor table for each user
    for u in users_data:
        d = models.Donor(
            name=u.name,
            phone=u.phone,
            blood_group=u.blood_group,
            city=u.location,
            latitude=u.latitude,
            longitude=u.longitude,
            availability=u.availability,
            is_verified=True,
            last_donation_date=u.last_donation_date,
            donation_type=u.donation_type,
            user_id=u.id
        )
        db.add(d)
    db.commit()

    # Seed demo emergency: Akalya requested for patient Sathya at KMCH
    demo_request = models.EmergencyRequest(
        user_id=users_data[0].id,
        requester_name="Akalya M",
        patient_name="Sathya (Father)",
        hospital_name="KMCH",
        hospital_city="Coimbatore",
        latitude=11.0267,
        longitude=77.0348,
        resource_type="blood",
        component="whole_blood",
        blood_group="O+",
        units_needed=2,
        units_accepted=0,
        urgency="URGENT",
        contact_phone="+91 94433 12345",
        status="SEARCHING",
        current_cascade_round=1,
        notes="Accident patient Sathya urgently requires 2 units O+ blood at KMCH."
    )
    db.add(demo_request)
    db.commit()

    # Immediately run matching & notifications for the demo emergency
    matches = matching.find_matches_for_request(db=db, emergency_request=demo_request)
    if matches["matches"]:
        notifications_service.notify_compatible_available_donors(
            db=db,
            emergency_request=demo_request,
            matched_donors=matches["matches"],
            round_num=1
        )
        demo_request.status = "COMPATIBLE_DONORS_FOUND"
        db.commit()

    # Seed past donation history for Arun Kumar
    past_donation = models.Donation(
        user_id=users_data[2].id,
        hospital_name="KMCH",
        blood_group="O+",
        component="whole_blood",
        units=1,
        donation_date=date.today() - timedelta(days=120),
        status="COMPLETED",
        notes="Voluntary donation for trauma surgery"
    )
    db.add(past_donation)
    db.commit()

    return {
        "message": "Demo data successfully seeded!",
        "users_added": len(users_data),
        "demo_emergency_id": demo_request.id
    }
