# LIFE-LINK
### AI-Powered Emergency Medical Resource & Donor Coordination Network

A clean, hackathon-friendly prototype built with Python, FastAPI, SQLAlchemy, and SQLite.

---

## Current Status: ALL PHASES COMPLETE ✅

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Backend + SQLite Foundation | ✅ Complete |
| Phase 2 | Intelligent Medical Resource Matching | ✅ Complete |
| Phase 3 | Adaptive Emergency Cascade | ✅ Complete |
| Phase 4 | Multilingual AI Emergency Request Bot | ✅ Complete |
| Phase 5 | Real Website (HTML/CSS/JS Frontend) | ✅ Complete |

---

## PHASE 5 — REAL WEBSITE

### What Was Built
A complete, functional website accessible at `http://127.0.0.1:5500` — no Swagger UI needed for the demo.

### Pages

| Page | URL | Purpose |
|------|-----|---------|
| **Home** | `index.html` | Live stats, workflow overview, seed demo data |
| **Emergency Help** | `emergency.html` | Natural-language / voice emergency request (AI-powered) |
| **Live Tracker** | `tracker.html` | Real-time emergency status, cascade timeline, matched donors |
| **Donor Portal** | `donor.html` | Register, toggle availability, view & respond to emergency alerts |
| **Hospital Dashboard** | `hospital.html` | Analytics, emergency table, blood inventory overview |
| **Organ & Tissue** | `organ.html` | Education-only organ donation info + NOTTO/TNOS routing |

### Phase 5 Backend Additions
Two new endpoints added to `main.py`:

```
POST  /emergency-requests/{request_id}/respond   — Donor ACCEPT or DECLINE
PATCH /donors/{donor_id}/availability            — Toggle donor availability
```

### Demo Flow (No Swagger Needed)
1. Open `http://127.0.0.1:5500`
2. Click **Seed Demo Data** (first time only)
3. Click **Emergency Help**
4. Type: `KMCH la O positive blood rendu units urgent ah venum`
5. Click **Understand Request** → AI parses fields
6. Review parsed fields → Click **Confirm & Create Emergency**
7. Page redirects to **Live Tracker** showing cascade + matched donors
8. Open **Donor Portal** → Select a donor → Click **Accept** on an alert
9. Tracker updates to show accepted units

---

## PHASE 4 — AI EMERGENCY REQUEST BOT

### Complete Pipeline Architecture
```
User Input (Voice / Text)
        ↓
AI Request Parser (English / Tanglish / Tamil)
        ↓
EmergencyRequest (Saved to Existing SQLite DB)
        ↓
Phase 2 Matching Engine (Haversine & Compatibility)
        ↓
Phase 3 Adaptive Cascade (Progressive Expansion)
        ↓
Matched Donors & Command Center
```

### What the AI Parser Does
Parses unstructured natural-language messages and extracts:
1. `resource_type` (e.g. `blood`)
2. `component` (e.g. `whole_blood`, `platelets`, `plasma`, `packed_rbc`)
3. `blood_group` (e.g. `O+`, `O-`, `A+`, `B+`, `AB+`, etc.)
4. `units_required` (e.g. `2`, `3`, `4`)
5. `hospital_name` (e.g. `KMCH`, `PSG Hospitals`, `GKNM`, etc.)
6. `urgency` (`CRITICAL`, `URGENT`, `NORMAL`)
7. `contact_phone` (if explicitly stated)

> **Important Safety Note**: The AI emergency bot **never diagnoses medical conditions** or suggests treatments.
> It functions exclusively as a natural-language emergency resource coordination assistant.

### Multilingual Support
- **English**: *"I need 2 units of O positive blood at KMCH urgently."*
- **Tanglish**: *"KMCH la O positive blood rendu units urgent ah venum."*
- **Tamil**: *"KMCH மருத்துவமனையில் O positive இரத்தம் இரண்டு யூனிட் அவசரமாக தேவை."*

### Handling Missing Information
- Parser does **NOT** guess or invent missing fields.
- Returns `success: false` and lists `missing_fields`.
- Produces a polite conversational follow-up prompt.

---

## PHASE 3 — ADAPTIVE EMERGENCY CASCADE

Configurable search bands:
- **Round 1**: 0–5 km
- **Round 2**: 5–15 km
- **Round 3**: 15–25 km
- **Round 4**: 25+ km / Verified Blood Banks

Stops as soon as the required number of units are found. If all rounds are exhausted, it flags `PARTIALLY_FULFILLED` or `NO_MATCHES` and recommends blood bank escalation.

---

## PHASE 2 — INTELLIGENT MATCHING

- Haversine distance formula (accurate km calculation from hospital coordinates)
- Full blood compatibility matrix (O-, O+, A-, A+, B-, B+, AB-, AB+)
- Availability filter (only `AVAILABLE` donors shown)
- Recent-donation eligibility (90-day cooldown check flag)
- Results sorted nearest-first

---

## Project Structure

```
life-link/
├── backend/
│   ├── database.py       # SQLite connection & session management
│   ├── models.py         # SQLAlchemy models (Donor, EmergencyRequest)
│   ├── schemas.py        # Pydantic schemas (all phases)
│   ├── matching.py       # Matching engine (compatibility + Haversine distance)
│   ├── cascade.py        # Adaptive Cascade engine (progressive expansion & deduplication)
│   ├── ai_parser.py      # Multilingual AI Emergency Request Parser
│   ├── main.py           # FastAPI routes & endpoints (all phases)
│   ├── test_phase1.py    # Automated test script - Phase 1
│   ├── test_phase2.py    # Automated test script - Phase 2
│   ├── test_phase3.py    # Automated test script - Phase 3
│   ├── test_phase4.py    # Automated test script - Phase 4 & End-to-End pipeline
│   ├── test_phase5.py    # Automated test script - Phase 5 (respond & availability)
│   ├── requirements.txt  # Dependencies (fastapi, uvicorn, sqlalchemy)
│   └── lifelink.db       # Local SQLite database (auto-created)
├── frontend/
│   ├── css/
│   │   └── style.css     # Full CSS stylesheet (dark medical theme)
│   ├── js/
│   │   └── app.js        # API client (LifeLinkAPI), SpeechHelper, showToast
│   ├── index.html        # Home page
│   ├── emergency.html    # Emergency request page (AI + voice input)
│   ├── tracker.html      # Live Command Center (cascade + matched donors)
│   ├── donor.html        # Donor Portal (register, availability, alerts)
│   ├── hospital.html     # Hospital Dashboard (analytics + emergency table)
│   └── organ.html        # Organ & Tissue info (education + NOTTO/TNOS routing)
└── README.md
```

---

## Backend API Endpoints

```
GET   /                                                  Health check
POST  /donors                                            Register a donor
GET   /donors                                            List donors (filterable)
GET   /donors/{donor_id}                                 Get single donor
PATCH /donors/{donor_id}/availability                    Update donor availability
POST  /emergency-requests                                Create emergency request
GET   /emergency-requests                                List emergency requests
GET   /emergency-requests/{request_id}                   Get single request
GET   /emergency-requests/{request_id}/matches           Phase 2: Find matching donors
GET   /emergency-requests/{request_id}/cascade           Phase 3: Adaptive cascade
POST  /emergency-requests/{request_id}/respond           Phase 5: Donor accept/decline
POST  /ai/parse-request                                  Phase 4: AI parse (no DB)
POST  /ai/create-emergency-from-text                     Phase 4: AI parse + create in DB
POST  /seed-demo-data                                    Seed sample donors & emergency
```

---

## How to Run

### Step 1 — Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 2 — Start the Backend (Terminal 1)
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Step 3 — Start the Frontend (Terminal 2)
```bash
python -m http.server 5500 --directory frontend
```

### Step 4 — Open the Website
Visit: [http://127.0.0.1:5500](http://127.0.0.1:5500)

### Run All Tests
```bash
cd backend
python test_phase1.py
python test_phase2.py
python test_phase3.py
python test_phase4.py
python test_phase5.py
```

### Swagger UI (Optional)
Visit: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Organ & Tissue — Safety Note

Life-Link **does NOT** directly match patients with organ donors or maintain an organ transplant waitlist.

The Organ & Tissue page (`organ.html`) is strictly:
- Educational (what can be donated, myths vs facts, brain stem death)
- Routing-only (directs users to NOTTO / TNOS / ZTCC Tamil Nadu)
- An information request form that records enquiries for proper authority routing

This is consistent with how organ transplantation actually works in India — regulated exclusively by authorised transplant authorities.
