"""
Life-Link Phase 4 Automated Test Suite
Tests for Multilingual AI Emergency Request Bot and End-to-End Pipeline:
1. English request parsing
2. Tanglish request parsing
3. Tamil request parsing
4. Blood group variations (O+, O positive, A-, B pos, AB+, etc.)
5. Natural language quantities (2 units, rendu units, இரண்டு யூனிட், 3 bottles)
6. Hospital extraction (KMCH, PSG Hospitals, Ganga, etc.)
7. Urgency classification (CRITICAL vs URGENT vs NORMAL)
8. Missing field detection & conversational prompt (does not invent info)
9. CRITICAL End-to-End Test:
   Natural Language Input -> AI Parser -> Existing EmergencyRequest DB ->
   Phase 2 Matching Engine -> Phase 3 Adaptive Cascade
"""

from fastapi.testclient import TestClient
from main import app
import ai_parser

client = TestClient(app)


def test_ai_parser_standalone():
    print("\n--- 1. Testing Standalone AI Multilingual Parser ---")

    # 1. English
    en_msg = "I need 2 units of O positive blood at KMCH urgently."
    res_en = ai_parser.parse_emergency_message(en_msg)
    assert res_en["success"] is True
    assert res_en["parsed_request"]["blood_group"] == "O+"
    assert res_en["parsed_request"]["units_required"] == 2
    assert res_en["parsed_request"]["hospital_name"] == "KMCH"
    assert res_en["parsed_request"]["urgency"] in ["URGENT", "CRITICAL"]
    print(f" -> [English] OK: {res_en['parsed_request']}")

    # 2. Tanglish
    tang_msg = "KMCH la O positive blood rendu units urgent ah venum."
    res_tang = ai_parser.parse_emergency_message(tang_msg)
    assert res_tang["success"] is True
    assert res_tang["parsed_request"]["blood_group"] == "O+"
    assert res_tang["parsed_request"]["units_required"] == 2
    assert res_tang["parsed_request"]["hospital_name"] == "KMCH"
    assert res_tang["parsed_request"]["urgency"] in ["URGENT", "CRITICAL"]
    print(f" -> [Tanglish] OK: {res_tang['parsed_request']}")

    # 3. Tamil
    tamil_msg = "KMCH மருத்துவமனையில் O positive இரத்தம் இரண்டு யூனிட் அவசரமாக தேவை."
    res_tamil = ai_parser.parse_emergency_message(tamil_msg)
    assert res_tamil["success"] is True
    assert res_tamil["parsed_request"]["blood_group"] == "O+"
    assert res_tamil["parsed_request"]["units_required"] == 2
    assert res_tamil["parsed_request"]["hospital_name"] == "KMCH"
    assert res_tamil["parsed_request"]["urgency"] == "CRITICAL"
    print(f" -> [Tamil] OK: {res_tamil['parsed_request']}")


def test_field_variations_and_safety():
    print("\n--- 2. Testing Field Variations and Missing Fields Safety ---")

    # Blood group variations
    assert ai_parser.extract_blood_group("Need A- blood") == "A-"
    assert ai_parser.extract_blood_group("patient requires B positive blood") == "B+"
    assert ai_parser.extract_blood_group("AB+ required") == "AB+"
    assert ai_parser.extract_blood_group("O negative blood") == "O-"
    assert ai_parser.extract_blood_group("XYZ blood") is None
    print(" -> Blood group extraction variations verified.")

    # Quantity variations
    assert ai_parser.extract_units("3 units needed") == 3
    assert ai_parser.extract_units("rendu units") == 2
    assert ai_parser.extract_units("moonu bottles") == 3
    assert ai_parser.extract_units("four packets") == 4
    assert ai_parser.extract_units("இரண்டு யூனிட்") == 2
    print(" -> Natural language quantity variations verified.")

    # Missing fields: user says only "I need blood urgently."
    partial_msg = "I need blood urgently."
    res_partial = ai_parser.parse_emergency_message(partial_msg)
    assert res_partial["success"] is False
    assert "blood_group" in res_partial["missing_fields"]
    assert "units_required" in res_partial["missing_fields"]
    assert "hospital_name" in res_partial["missing_fields"]
    # Check that system does NOT invent missing values
    assert res_partial["parsed_request"]["blood_group"] is None
    assert res_partial["parsed_request"]["units_required"] is None
    assert res_partial["parsed_request"]["hospital_name"] is None
    print(f" -> Missing fields correctly identified: {res_partial['missing_fields']}")
    print(f" -> Conversational prompt generated: '{res_partial['message']}'")


def test_ai_api_endpoints():
    print("\n--- 3. Testing FastAPI AI Parser Endpoints ---")
    
    # POST /ai/parse-request (Parse only)
    payload_parse = {
        "message": "Accident at PSG Hospitals, need 3 units of B+ blood immediately"
    }
    res = client.post("/ai/parse-request", json=payload_parse)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["parsed_request"]["blood_group"] == "B+"
    assert data["parsed_request"]["units_required"] == 3
    assert "PSG" in data["parsed_request"]["hospital_name"]
    assert data["parsed_request"]["urgency"] == "CRITICAL"
    print(" -> POST /ai/parse-request successfully returned structured JSON.")


def test_critical_end_to_end_pipeline():
    print("\n--- 4. CRITICAL END-TO-END PIPELINE INTEGRATION TEST ---")
    print(" Flow: User Text -> AI Parser -> Existing DB -> Phase 2 Matcher -> Phase 3 Cascade")
    
    # Ensure demo database is seeded
    client.post("/seed-demo-data")

    # Step 1: User speaks / types natural language emergency in Tanglish
    user_input = "KMCH la O positive blood 2 units urgent ah venum"
    print(f"\n[Step 1] User Natural Language Input: \"{user_input}\"")

    # Step 2: Send to AI endpoint with auto_create=True
    ai_req_payload = {
        "message": user_input,
        "auto_create": True,
        "contact_phone": "+91 94433 88888"
    }
    ai_response = client.post("/ai/parse-request", json=ai_req_payload)
    assert ai_response.status_code == 200
    ai_data = ai_response.json()

    assert ai_data["success"] is True
    assert ai_data["created_emergency_request_id"] is not None
    created_id = ai_data["created_emergency_request_id"]
    print(f"[Step 2] AI Parsed and created Emergency Request #{created_id} in existing database!")
    print(f"         Hospital: {ai_data['parsed_request']['hospital_name']}")
    print(f"         Blood: {ai_data['parsed_request']['blood_group']}")
    print(f"         Units: {ai_data['parsed_request']['units_required']}")
    print(f"         Urgency: {ai_data['parsed_request']['urgency']}")

    # Step 3: Trigger existing Phase 2 Matching Engine using this new request ID
    print(f"\n[Step 3] Querying Phase 2 Matching Engine: GET /emergency-requests/{created_id}/matches")
    res_matches = client.get(f"/emergency-requests/{created_id}/matches")
    assert res_matches.status_code == 200
    match_data = res_matches.json()
    print(f"         Total compatible donors found: {match_data['total_compatible_found']}")
    assert match_data["total_compatible_found"] > 0
    closest_donor = match_data["matches"][0]
    print(f"         Closest donor: {closest_donor['name']} ({closest_donor['distance_km']} km away)")

    # Step 4: Trigger existing Phase 3 Adaptive Cascade using this new request ID
    print(f"\n[Step 4] Querying Phase 3 Adaptive Cascade: GET /emergency-requests/{created_id}/cascade")
    res_cascade = client.get(f"/emergency-requests/{created_id}/cascade")
    assert res_cascade.status_code == 200
    cascade_data = res_cascade.json()
    print(f"         Cascade Status: {cascade_data['status']}")
    print(f"         Units Required: {cascade_data['units_required']}, Matched: {cascade_data['units_matched']}")
    print(f"         Rounds Executed: {len(cascade_data['rounds'])}")
    assert cascade_data["status"] == "TARGET_REACHED"
    assert cascade_data["units_matched"] >= 2

    # Step 5: Verify EmergencyRequest record in database reflects the updated status
    db_verify = client.get(f"/emergency-requests/{created_id}")
    assert db_verify.status_code == 200
    assert db_verify.json()["status"] == "TARGET_REACHED"
    print(f"\n[Step 5] Verified DB persistence: Emergency #{created_id} status is '{db_verify.json()['status']}'")

    print("\n" + "=" * 65)
    print("CRITICAL END-TO-END PIPELINE PASSED 100%!")
    print("=" * 65)


def run_all_phase4_tests():
    print("=" * 65)
    print("RUNNING LIFE-LINK PHASE 4 AI EMERGENCY PARSER TESTS")
    print("=" * 65)
    test_ai_parser_standalone()
    test_field_variations_and_safety()
    test_ai_api_endpoints()
    test_critical_end_to_end_pipeline()
    print("\n" + "=" * 65)
    print("ALL PHASE 4 TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 65)


if __name__ == "__main__":
    run_all_phase4_tests()
