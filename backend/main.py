"""
Life-Link: Main FastAPI Application
AI-Powered Emergency Medical Resource & Donor Coordination Network

Phase 1: Core Backend + SQLite Setup
- Donor Registration & Retrieval
- Emergency Request Creation & Tracking
- Demo Data Seeding for Easy Hackathon Testing
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta

import models
import schemas
import matching
import cascade
import ai_parser
from database import engine, get_db

# Create database tables automatically on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Life-Link Emergency Resource Coordination API",
    description="Emergency Medical Resource & Donor Coordination Network prototype for hackathons.",
    version="1.0.0"
)

# Enable CORS so any frontend (HTML/JS) can call these endpoints smoothly.
# NOTE: allow_credentials=True is incompatible with allow_origins=["*"] per the CORS spec —
# browsers block responses that have both. Since this app uses no cookies or auth headers,
# credentials are not needed. Explicit origins are listed to cover both Live Server addresses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "null",  # file:// protocol (opening HTML directly from filesystem)
    ],
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
        "version": "1.0.0 (Phase 1: Backend + SQLite)",
        "docs_url": "/docs"
    }


# ==========================================
# DONOR ENDPOINTS
# ==========================================

@app.post("/donors", response_model=schemas.DonorResponse, status_code=status.HTTP_201_CREATED)
def create_donor(donor: schemas.DonorCreate, db: Session = Depends(get_db)):
    """
    Register a new voluntary blood donor.
    """
    # Clean blood group string (e.g., 'o+' -> 'O+')
    clean_blood_group = donor.blood_group.strip().upper()

    db_donor = models.Donor(
        name=donor.name.strip(),
        phone=donor.phone.strip(),
        blood_group=clean_blood_group,
        city=donor.city.strip() if donor.city else "Coimbatore",
        latitude=donor.latitude or 11.0168,
        longitude=donor.longitude or 76.9558,
        availability=(donor.availability or "AVAILABLE").upper(),
        is_verified=True,  # Default to verified for prototype
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
        # In URLs, '+' is often converted to a space ' ' (e.g. 'O+' becomes 'O ')
        # We replace spaces with '+' to handle both 'O+' and 'O%2B' reliably.
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


# ==========================================
# EMERGENCY REQUEST ENDPOINTS
# ==========================================

@app.post("/emergency-requests", response_model=schemas.EmergencyRequestResponse, status_code=status.HTTP_201_CREATED)
def create_emergency_request(
    request: schemas.EmergencyRequestCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new emergency blood or component request.
    """
    clean_blood_group = request.blood_group.strip().upper()

    db_request = models.EmergencyRequest(
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
# PHASE 2: MATCHING ENDPOINT
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
# PHASE 3: ADAPTIVE EMERGENCY CASCADE ENDPOINT
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
# PHASE 4: MULTILINGUAL AI EMERGENCY BOT
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
    parse_result = ai_parser.parse_emergency_message(payload.message)
    
    created_id = None
    created_obj = None

    # If parsing succeeded and auto_create is requested, pipe directly into Phase 1 DB!
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
            patient_name="Emergency Patient (AI Bot)",
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
    parse_result = ai_parser.parse_emergency_message(payload.message)
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
        patient_name="Emergency Patient (AI Bot)",
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
# PHASE 5: DONOR RESPONSE & AVAILABILITY ENDPOINTS
# ==========================================

@app.post("/emergency-requests/{request_id}/respond", response_model=schemas.DonorResponseResult)
def respond_to_emergency(
    request_id: int,
    action_data: schemas.DonorResponseAction,
    db: Session = Depends(get_db)
):
    """
    Allows a matched donor to ACCEPT or DECLINE an emergency request.
    Increments units_accepted when accepted, and updates status if target is reached.
    """
    req = db.query(models.EmergencyRequest).filter(models.EmergencyRequest.id == request_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency request with ID {request_id} not found"
        )

    donor = db.query(models.Donor).filter(models.Donor.id == action_data.donor_id).first()
    if not donor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Donor with ID {action_data.donor_id} not found"
        )

    clean_action = action_data.action.strip().upper()
    if clean_action == "ACCEPT":
        req.units_accepted += 1
        if req.units_accepted >= req.units_needed:
            req.status = "TARGET_REACHED"
        else:
            req.status = "DONOR_ACCEPTED"
        message = f"Thank you, {donor.name}! Your acceptance has been registered. The hospital has been notified."
    else:
        clean_action = "DECLINE"
        message = f"Thank you for letting us know, {donor.name}. The request has been declined."

    db.commit()
    db.refresh(req)

    return {
        "emergency_request_id": req.id,
        "donor_id": donor.id,
        "action": clean_action,
        "units_needed": req.units_needed,
        "units_accepted": req.units_accepted,
        "status": req.status,
        "message": message
    }


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
    db.commit()
    db.refresh(donor)
    return donor


# ==========================================
# DEMO DATA SEEDING HELPER
# ==========================================

@app.post("/seed-demo-data")
def seed_demo_data(db: Session = Depends(get_db)):
    """
    Convenient helper endpoint to seed realistic sample donors and a demo emergency request
    around Coimbatore / KMCH hospital for instant hackathon testing.
    """
    # Check if donors already exist
    existing_count = db.query(models.Donor).count()
    if existing_count > 0:
        return {
            "message": f"Database already contains {existing_count} donors. Skipping seed.",
            "total_donors": existing_count
        }

    # Reference Hospital: KMCH Coimbatore (Lat: 11.0267, Lon: 77.0348)
    sample_donors = [
        # Donors close by (Round 1: 0 - 5 km)
        models.Donor(
            name="Arun Kumar",
            phone="+91 98421 11001",
            blood_group="O+",
            city="Coimbatore (KMCH Area)",
            latitude=11.0350,
            longitude=77.0310,  # ~1.2 km
            availability="AVAILABLE",
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=120),
            donation_type="whole_blood"
        ),
        models.Donor(
            name="Priya Senthil",
            phone="+91 98421 11002",
            blood_group="O+",
            city="Coimbatore (Peelamedu)",
            latitude=11.0280,
            longitude=77.0120,  # ~2.5 km
            availability="AVAILABLE",
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=100),
            donation_type="whole_blood"
        ),
        models.Donor(
            name="Karthik R",
            phone="+91 98421 11003",
            blood_group="O-",  # Universal donor
            city="Coimbatore (Hopes College)",
            latitude=11.0240,
            longitude=77.0180,  # ~1.9 km
            availability="AVAILABLE",
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=150),
            donation_type="whole_blood"
        ),
        models.Donor(
            name="Divya M",
            phone="+91 98421 11004",
            blood_group="A+",
            city="Coimbatore (Sitra)",
            latitude=11.0390,
            longitude=77.0420,  # ~1.6 km
            availability="AVAILABLE",
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=95),
            donation_type="whole_blood"
        ),
        # Donors in mid-range (Round 2: 5 - 15 km)
        models.Donor(
            name="Suresh Balaji",
            phone="+91 98421 11005",
            blood_group="O+",
            city="Coimbatore (Gandhipuram)",
            latitude=11.0183,
            longitude=76.9669,  # ~7.4 km
            availability="AVAILABLE",
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=110),
            donation_type="whole_blood"
        ),
        models.Donor(
            name="Ananya Lakshmi",
            phone="+91 98421 11006",
            blood_group="O+",
            city="Coimbatore (RS Puram)",
            latitude=11.0080,
            longitude=76.9450,  # ~10.1 km
            availability="AVAILABLE",
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=130),
            donation_type="whole_blood"
        ),
        models.Donor(
            name="Vignesh K",
            phone="+91 98421 11007",
            blood_group="B+",
            city="Coimbatore (Saibaba Colony)",
            latitude=11.0290,
            longitude=76.9420,  # ~10.2 km
            availability="AVAILABLE",
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=140),
            donation_type="whole_blood"
        ),
        # Donors in outer-range (Round 3: 15 - 25 km)
        models.Donor(
            name="Deepak Natarajan",
            phone="+91 98421 11008",
            blood_group="O+",
            city="Coimbatore Outskirts (Sulur)",
            latitude=11.0270,
            longitude=77.1260,  # ~16.5 km
            availability="AVAILABLE",
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=180),
            donation_type="whole_blood"
        ),
        # Ineligible donor (recently donated 20 days ago)
        models.Donor(
            name="Manoj C",
            phone="+91 98421 11009",
            blood_group="O+",
            city="Coimbatore (Peelamedu)",
            latitude=11.0290,
            longitude=77.0150,  # ~2.2 km
            availability="AVAILABLE",
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=20),  # Not eligible (<90 days)
            donation_type="whole_blood"
        ),
        # Unavailable donor
        models.Donor(
            name="Rahul V",
            phone="+91 98421 11010",
            blood_group="O+",
            city="Coimbatore (Singanallur)",
            latitude=11.0010,
            longitude=77.0210,  # ~3.2 km
            availability="UNAVAILABLE",  # Unavailable
            is_verified=True,
            last_donation_date=date.today() - timedelta(days=150),
            donation_type="whole_blood"
        )
    ]

    db.add_all(sample_donors)

    # Also add an initial sample emergency request
    sample_request = models.EmergencyRequest(
        patient_name="Accident Patient (ICU Bed 4)",
        hospital_name="KMCH",
        hospital_city="Coimbatore",
        latitude=11.0267,
        longitude=77.0348,
        resource_type="blood",
        component="whole_blood",
        blood_group="O+",
        units_needed=3,
        units_accepted=0,
        urgency="CRITICAL",
        contact_phone="+91 94433 99999",
        status="SEARCHING",
        current_cascade_round=1,
        notes="Accident patient urgently requires 3 units of O+ blood at KMCH emergency ward."
    )
    db.add(sample_request)

    db.commit()

    return {
        "message": "Demo data successfully seeded!",
        "donors_added": len(sample_donors),
        "sample_emergency_request_id": sample_request.id
    }
