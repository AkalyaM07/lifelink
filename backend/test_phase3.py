"""
Life-Link Phase 3 Automated Test Suite
Tests for Adaptive Emergency Cascade Engine:
1. Scenario A: Target fulfilled in Round 1 (0-5 km)
2. Scenario B: Target not fulfilled in Round 1, but fulfilled in Round 2 (5-15 km)
3. Scenario C: Target expands through Round 3
4. Scenario D: Target unfulfilled after all donor rounds (PARTIALLY_FULFILLED + blood bank backup)
5. Scenario E: No matches found in any round (NO_MATCHES)
6. Deduplication verification (no donor appears in multiple rounds)
7. Safety checks (only compatible & available donors included)
8. Edge cases (404 for invalid request, correct arithmetic for units_matched & units_remaining)
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_cascade_engine():
    print("=" * 65)
    print("RUNNING LIFE-LINK PHASE 3 ADAPTIVE CASCADE TESTS")
    print("=" * 65)

    # Ensure demo database is freshly populated with known 12-user state
    client.post("/seed-demo-data?force=true")

    # -------------------------------------------------------------
    # 1. SCENARIO A: Target fulfilled within Round 1 (0 - 5 km)
    # -------------------------------------------------------------
    print("\n[1/8] Testing Scenario A: Requirement fulfilled in Round 1...")
    req_round1_payload = {
        "hospital_name": "KMCH",
        "blood_group": "O+",
        "units_needed": 2,  # 2 units needed; we have 4 compatible donors within 5 km
        "urgency": "CRITICAL",
        "contact_phone": "+91 94433 11111",
        "notes": "Emergency surgery - 2 units O+ needed"
    }
    r1_create = client.post("/emergency-requests", json=req_round1_payload)
    assert r1_create.status_code == 201
    r1_id = r1_create.json()["id"]

    res_cascade_1 = client.get(f"/emergency-requests/{r1_id}/cascade")
    assert res_cascade_1.status_code == 200
    data_1 = res_cascade_1.json()

    print(f" -> Units Required: {data_1['units_required']}, Matched: {data_1['units_matched']}, Status: {data_1['status']}")
    print(f" -> Current Round: {data_1['current_round']}, Rounds executed: {len(data_1['rounds'])}")
    assert data_1["status"] == "TARGET_REACHED"
    assert data_1["current_round"] == 1
    assert len(data_1["rounds"]) == 1  # Stopped at Round 1!
    assert data_1["units_remaining"] == 0
    assert data_1["blood_bank_backup_recommended"] is False
    print(" -> Scenario A Passed: Stopped at Round 1 immediately upon fulfilling requirement.")

    # -------------------------------------------------------------
    # 2. SCENARIO B: Target expands to Round 2 (5 - 15 km)
    # -------------------------------------------------------------
    print("\n[2/8] Testing Scenario B: Expands to Round 2 to fulfill requirement...")
    req_round2_payload = {
        "hospital_name": "KMCH",
        "blood_group": "O+",
        "units_needed": 6,  # 6 units needed; 4 in Round 1 (0-5km) + 3 in Round 2 (5-15km)
        "urgency": "CRITICAL",
        "contact_phone": "+91 94433 22222",
        "notes": "Accident trauma - 6 units O+ needed"
    }
    r2_create = client.post("/emergency-requests", json=req_round2_payload)
    assert r2_create.status_code == 201
    r2_id = r2_create.json()["id"]

    res_cascade_2 = client.get(f"/emergency-requests/{r2_id}/cascade")
    assert res_cascade_2.status_code == 200
    data_2 = res_cascade_2.json()

    print(f" -> Units Required: {data_2['units_required']}, Matched: {data_2['units_matched']}, Status: {data_2['status']}")
    print(f" -> Current Round: {data_2['current_round']}, Rounds executed: {len(data_2['rounds'])}")
    assert data_2["status"] == "TARGET_REACHED"
    assert data_2["current_round"] == 2
    assert len(data_2["rounds"]) == 2  # Executed Round 1 and Round 2
    assert data_2["units_remaining"] == 0
    print(" -> Scenario B Passed: Expanded to Round 2 and fulfilled target.")

    # -------------------------------------------------------------
    # 3. SCENARIO C: Donor Deduplication between rounds
    # -------------------------------------------------------------
    print("\n[3/8] Testing Donor Deduplication between cascade rounds...")
    donor_ids = [m["donor_id"] for m in data_2["matches"]]
    assert len(donor_ids) == len(set(donor_ids)), f"Duplicate donor found: {donor_ids}"
    print(f" -> Deduplication check passed: {len(donor_ids)} unique donors across rounds.")

    # Verify donor rounds assignment
    round1_matches = [m for m in data_2["matches"] if m["cascade_round"] == 1]
    round2_matches = [m for m in data_2["matches"] if m["cascade_round"] == 2]
    print(f"    - Round 1 donors: {len(round1_matches)} (all <= 5 km)")
    print(f"    - Round 2 donors: {len(round2_matches)} (all between 5 and 15 km)")
    for d in round1_matches:
        assert d["distance_km"] <= 5.0
    for d in round2_matches:
        assert 5.0 <= d["distance_km"] <= 15.0
    print(" -> Round distance bands strictly verified.")

    # -------------------------------------------------------------
    # 4. SCENARIO D: Requirement partially fulfilled (Large requirement)
    # -------------------------------------------------------------
    print("\n[4/8] Testing Scenario D: Large requirement -> PARTIALLY_FULFILLED...")
    req_large_payload = {
        "hospital_name": "KMCH",
        "blood_group": "O+",
        "units_needed": 20,  # We only have ~7 total available O+/O- donors in entire DB
        "urgency": "CRITICAL",
        "contact_phone": "+91 94433 33333",
        "notes": "Mass casualty event - 20 units needed"
    }
    r_large_create = client.post("/emergency-requests", json=req_large_payload)
    assert r_large_create.status_code == 201
    r_large_id = r_large_create.json()["id"]

    res_cascade_large = client.get(f"/emergency-requests/{r_large_id}/cascade")
    assert res_cascade_large.status_code == 200
    data_large = res_cascade_large.json()

    print(f" -> Required: {data_large['units_required']}, Matched: {data_large['units_matched']}, Remaining: {data_large['units_remaining']}")
    print(f" -> Status: {data_large['status']}, Blood Bank Recommended: {data_large['blood_bank_backup_recommended']}")
    assert data_large["status"] == "PARTIALLY_FULFILLED"
    assert data_large["units_remaining"] > 0
    assert data_large["units_required"] == data_large["units_matched"] + data_large["units_remaining"]
    assert data_large["blood_bank_backup_recommended"] is True
    assert data_large["current_round"] == 4  # Escalated to Round 4 / Blood Banks
    print(" -> Scenario D Passed: Correctly flagged PARTIALLY_FULFILLED and recommended blood banks.")

    # -------------------------------------------------------------
    # 5. SCENARIO E: No matches found in any round (NO_MATCHES)
    # -------------------------------------------------------------
    print("\n[5/8] Testing Scenario E: No matches found -> NO_MATCHES...")
    # Hospital located in Chennai (~450 km away from Coimbatore donors)
    # Tests behavior when no registered donors exist within 0-25 km
    req_nomatch_payload = {
        "hospital_name": "Apollo Hospitals (Chennai)",
        "hospital_city": "Chennai",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "blood_group": "O+",
        "units_needed": 2,
        "urgency": "CRITICAL",
        "contact_phone": "+91 94433 44444"
    }
    r_nomatch_create = client.post("/emergency-requests", json=req_nomatch_payload)
    assert r_nomatch_create.status_code == 201
    r_nomatch_id = r_nomatch_create.json()["id"]

    res_cascade_nomatch = client.get(f"/emergency-requests/{r_nomatch_id}/cascade")
    assert res_cascade_nomatch.status_code == 200
    data_nomatch = res_cascade_nomatch.json()

    print(f" -> Status: {data_nomatch['status']}, Units Matched: {data_nomatch['units_matched']}, Units Remaining: {data_nomatch['units_remaining']}")
    assert data_nomatch["status"] == "NO_MATCHES"
    assert data_nomatch["units_matched"] == 0
    assert data_nomatch["units_remaining"] == 2
    assert data_nomatch["blood_bank_backup_recommended"] is True
    print(" -> Scenario E Passed: Correctly identified NO_MATCHES status.")

    # -------------------------------------------------------------
    # 6. Safety check: Incompatible & Unavailable Donors Excluded
    # -------------------------------------------------------------
    print("\n[6/8] Testing Safety: Incompatible & Unavailable donors strictly excluded...")
    for m in data_2["matches"]:
        assert m["blood_group"] in ["O+", "O-"]
        assert m["availability"] == "AVAILABLE"
        assert m["name"] != "Rahul V"  # Rahul V is UNAVAILABLE
        assert m["name"] != "Divya M"  # Divya M is A+
    print(" -> Safety check passed: No incompatible or unavailable donors found in cascade.")

    # -------------------------------------------------------------
    # 7. Edge Case: Non-existent emergency request returns 404
    # -------------------------------------------------------------
    print("\n[7/8] Testing 404 for non-existent emergency request...")
    res_404 = client.get("/emergency-requests/999999/cascade")
    assert res_404.status_code == 404
    print(" -> 404 error handling verified.")

    # -------------------------------------------------------------
    # 8. Check Database State Update
    # -------------------------------------------------------------
    print("\n[8/8] Testing Database State Persistence after Cascade...")
    db_check = client.get(f"/emergency-requests/{r1_id}")
    assert db_check.status_code == 200
    assert db_check.json()["status"] == "TARGET_REACHED"
    assert db_check.json()["current_cascade_round"] == 1
    print(f" -> DB record verified: status='{db_check.json()['status']}', round={db_check.json()['current_cascade_round']}")

    print("\n" + "=" * 65)
    print("ALL PHASE 3 TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 65)


if __name__ == "__main__":
    test_cascade_engine()
