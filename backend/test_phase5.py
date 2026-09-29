"""
Life-Link: Phase 5 Tests
Tests for Phase 5 backend additions:
  - POST /emergency-requests/{id}/respond  (ACCEPT / DECLINE)
  - PATCH /donors/{id}/availability
"""

import sys
import os

# Make sure imports work when running from the backend directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starlette.testclient import TestClient
from main import app
from database import engine
import models

# ---- Test client (in-memory, uses real DB) ----
client = TestClient(app)

# ---- Colours for terminal output ----
GREEN = "\033[92m"
RED   = "\033[91m"
CYAN  = "\033[96m"
RESET = "\033[0m"

passed = 0
failed = 0


def ok(name):
    global passed
    passed += 1
    print(f"  {GREEN}PASS{RESET}  {name}")


def fail(name, reason=""):
    global failed
    failed += 1
    print(f"  {RED}FAIL{RESET}  {name}" + (f"  ->  {reason}" if reason else ""))


def section(title):
    print(f"\n{CYAN}{'-' * 60}{RESET}")
    print(f"{CYAN}  {title}{RESET}")
    print(f"{CYAN}{'-' * 60}{RESET}")


# =====================================================
# HELPERS -- create a clean donor and emergency request
# for each test scenario.
# =====================================================

def create_test_donor(blood_group="O+", availability="AVAILABLE"):
    """Create a fresh donor and return the donor dict."""
    resp = client.post("/donors", json={
        "name": "Phase5 Test Donor",
        "phone": "+91 90000 00000",
        "blood_group": blood_group,
        "city": "Coimbatore",
        "latitude": 11.0267,
        "longitude": 77.0348,
        "availability": availability,
        "donation_type": "whole_blood"
    })
    assert resp.status_code == 201, f"Donor creation failed: {resp.text}"
    return resp.json()


def create_test_emergency(units_needed=2, blood_group="O+"):
    """Create a fresh emergency request and return the request dict."""
    resp = client.post("/emergency-requests", json={
        "patient_name": "Test Patient P5",
        "hospital_name": "KMCH",
        "hospital_city": "Coimbatore",
        "latitude": 11.0267,
        "longitude": 77.0348,
        "resource_type": "blood",
        "component": "whole_blood",
        "blood_group": blood_group,
        "units_needed": units_needed,
        "urgency": "CRITICAL",
        "contact_phone": "+91 90000 99999"
    })
    assert resp.status_code == 201, f"Emergency creation failed: {resp.text}"
    return resp.json()


# =====================================================
# TEST SECTION 1 -- DONOR RESPONSE (ACCEPT / DECLINE)
# =====================================================

section("1. Donor ACCEPT Response")

# --- Test 1a: Donor accepts -- basic response ---
try:
    donor   = create_test_donor()
    req     = create_test_emergency(units_needed=3)
    donor_id = donor["id"]
    req_id   = req["id"]

    resp = client.post(f"/emergency-requests/{req_id}/respond", json={
        "donor_id": donor_id,
        "action": "ACCEPT"
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["action"] == "ACCEPT", f"Expected ACCEPT, got {data['action']}"
    assert data["units_accepted"] == 1, f"Expected units_accepted=1, got {data['units_accepted']}"
    assert data["emergency_request_id"] == req_id
    assert data["donor_id"] == donor_id
    ok("Donor ACCEPT -- returns 200 with correct units_accepted=1")
except Exception as e:
    fail("Donor ACCEPT -- returns 200 with correct units_accepted=1", str(e))


# --- Test 1b: units_accepted increments correctly on second ACCEPT ---
try:
    donor2 = create_test_donor()
    # Same emergency request from above (units_needed=3, currently accepted=1)
    resp2 = client.post(f"/emergency-requests/{req_id}/respond", json={
        "donor_id": donor2["id"],
        "action": "ACCEPT"
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["units_accepted"] == 2, f"Expected 2, got {data2['units_accepted']}"
    assert data2["status"] == "DONOR_ACCEPTED", f"Expected DONOR_ACCEPTED, got {data2['status']}"
    ok("Second ACCEPT -- units_accepted increments to 2, status=DONOR_ACCEPTED")
except Exception as e:
    fail("Second ACCEPT -- units_accepted increments", str(e))


# --- Test 1c: Target is reached when units_accepted >= units_needed ---
try:
    donor3 = create_test_donor()
    # units_needed=3, currently accepted=2 -- this accept should trigger TARGET_REACHED
    resp3 = client.post(f"/emergency-requests/{req_id}/respond", json={
        "donor_id": donor3["id"],
        "action": "ACCEPT"
    })
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["units_accepted"] == 3, f"Expected 3, got {data3['units_accepted']}"
    assert data3["status"] == "TARGET_REACHED", f"Expected TARGET_REACHED, got {data3['status']}"
    ok("Third ACCEPT -- units_accepted=3 -> status=TARGET_REACHED")
except Exception as e:
    fail("Third ACCEPT -- status becomes TARGET_REACHED", str(e))


# --- Test 1d: Verify emergency request status via GET ---
try:
    get_resp = client.get(f"/emergency-requests/{req_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["units_accepted"] == 3
    assert get_data["status"] == "TARGET_REACHED"
    ok("GET /emergency-requests/{id} confirms TARGET_REACHED and units_accepted=3")
except Exception as e:
    fail("GET /emergency-requests/{id} confirms updated status", str(e))


section("2. Donor DECLINE Response")

# --- Test 2a: Donor declines -- units_accepted should NOT change ---
try:
    d_donor = create_test_donor()
    d_req   = create_test_emergency(units_needed=2)
    resp = client.post(f"/emergency-requests/{d_req['id']}/respond", json={
        "donor_id": d_donor["id"],
        "action": "DECLINE"
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["action"] == "DECLINE", f"Expected DECLINE, got {data['action']}"
    assert data["units_accepted"] == 0, f"Expected 0 after DECLINE, got {data['units_accepted']}"
    ok("Donor DECLINE -- action=DECLINE, units_accepted stays at 0")
except Exception as e:
    fail("Donor DECLINE -- units_accepted unchanged", str(e))


# --- Test 2b: DECLINE response has a message ---
try:
    assert "message" in data, "Expected 'message' field in DECLINE response"
    assert len(data["message"]) > 0
    ok("DECLINE response includes a message field")
except Exception as e:
    fail("DECLINE response includes message", str(e))


# --- Test 2c: ACCEPT response includes donor name in message ---
try:
    a_donor = create_test_donor()
    a_req   = create_test_emergency(units_needed=1)
    resp = client.post(f"/emergency-requests/{a_req['id']}/respond", json={
        "donor_id": a_donor["id"],
        "action": "ACCEPT"
    })
    msg = resp.json().get("message", "")
    assert "Phase5 Test Donor" in msg, f"Donor name not in message: {msg}"
    ok("ACCEPT response message includes donor's name")
except Exception as e:
    fail("ACCEPT message includes donor name", str(e))


section("3. Invalid / Error Cases for /respond")

# --- Test 3a: Invalid emergency request ID -> 404 ---
try:
    donor = create_test_donor()
    resp = client.post("/emergency-requests/999999/respond", json={
        "donor_id": donor["id"],
        "action": "ACCEPT"
    })
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    ok("Non-existent emergency request ID -> 404")
except Exception as e:
    fail("Non-existent emergency request ID -> 404", str(e))


# --- Test 3b: Invalid donor ID -> 404 ---
try:
    req = create_test_emergency()
    resp = client.post(f"/emergency-requests/{req['id']}/respond", json={
        "donor_id": 999999,
        "action": "ACCEPT"
    })
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    ok("Non-existent donor ID -> 404")
except Exception as e:
    fail("Non-existent donor ID -> 404", str(e))


# --- Test 3c: Action is normalised (accept -> ACCEPT) ---
try:
    donor = create_test_donor()
    req   = create_test_emergency(units_needed=5)
    resp = client.post(f"/emergency-requests/{req['id']}/respond", json={
        "donor_id": donor["id"],
        "action": "accept"   # lowercase -- should be accepted
    })
    assert resp.status_code == 200
    assert resp.json()["action"] == "ACCEPT"
    ok("Lowercase 'accept' is normalised to 'ACCEPT'")
except Exception as e:
    fail("Action normalised to uppercase", str(e))


# --- Test 3d: Single-unit emergency reaches TARGET_REACHED after one ACCEPT ---
try:
    donor = create_test_donor()
    req   = create_test_emergency(units_needed=1)
    resp = client.post(f"/emergency-requests/{req['id']}/respond", json={
        "donor_id": donor["id"],
        "action": "ACCEPT"
    })
    data = resp.json()
    assert data["units_accepted"] == 1
    assert data["status"] == "TARGET_REACHED"
    ok("Single-unit emergency: one ACCEPT -> TARGET_REACHED immediately")
except Exception as e:
    fail("Single-unit emergency -> TARGET_REACHED", str(e))


# =====================================================
# TEST SECTION 4 -- DONOR AVAILABILITY UPDATE
# =====================================================

section("4. PATCH /donors/{id}/availability")

# --- Test 4a: Set to UNAVAILABLE ---
try:
    donor = create_test_donor(availability="AVAILABLE")
    resp = client.patch(f"/donors/{donor['id']}/availability", json={"availability": "UNAVAILABLE"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert resp.json()["availability"] == "UNAVAILABLE"
    ok("PATCH availability -> UNAVAILABLE")
except Exception as e:
    fail("PATCH availability -> UNAVAILABLE", str(e))


# --- Test 4b: Set to MAYBE_AVAILABLE ---
try:
    resp = client.patch(f"/donors/{donor['id']}/availability", json={"availability": "MAYBE_AVAILABLE"})
    assert resp.status_code == 200
    assert resp.json()["availability"] == "MAYBE_AVAILABLE"
    ok("PATCH availability -> MAYBE_AVAILABLE")
except Exception as e:
    fail("PATCH availability -> MAYBE_AVAILABLE", str(e))


# --- Test 4c: Set back to AVAILABLE ---
try:
    resp = client.patch(f"/donors/{donor['id']}/availability", json={"availability": "AVAILABLE"})
    assert resp.status_code == 200
    assert resp.json()["availability"] == "AVAILABLE"
    ok("PATCH availability -> AVAILABLE (toggle back)")
except Exception as e:
    fail("PATCH availability -> AVAILABLE", str(e))


# --- Test 4d: GET /donors/{id} reflects the updated availability ---
try:
    get_resp = client.get(f"/donors/{donor['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["availability"] == "AVAILABLE"
    ok("GET /donors/{id} confirms availability persisted in database")
except Exception as e:
    fail("GET /donors/{id} reflects updated availability", str(e))


# --- Test 4e: Invalid availability value -> 400 ---
try:
    resp = client.patch(f"/donors/{donor['id']}/availability", json={"availability": "BUSY"})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    ok("Invalid availability value 'BUSY' -> 400")
except Exception as e:
    fail("Invalid availability -> 400", str(e))


# --- Test 4f: Non-existent donor -> 404 ---
try:
    resp = client.patch("/donors/999999/availability", json={"availability": "AVAILABLE"})
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    ok("Non-existent donor ID for availability update -> 404")
except Exception as e:
    fail("Non-existent donor -> 404 on availability update", str(e))


# --- Test 4g: Case-insensitive input is handled ---
try:
    resp = client.patch(f"/donors/{donor['id']}/availability", json={"availability": "unavailable"})
    # The endpoint does .upper() so 'unavailable' -> 'UNAVAILABLE'
    assert resp.status_code == 200
    assert resp.json()["availability"] == "UNAVAILABLE"
    ok("Lowercase 'unavailable' is accepted and normalised to 'UNAVAILABLE'")
except Exception as e:
    fail("Availability value normalised to uppercase", str(e))


# =====================================================
# SUMMARY
# =====================================================

total = passed + failed
print(f"\n{'-' * 60}")
print(f"  Phase 5 Results:  {GREEN}{passed} passed{RESET}  |  {RED}{failed} failed{RESET}  |  {total} total")
print(f"{'-' * 60}\n")

if failed > 0:
    sys.exit(1)
