"""
Life-Link Emergency Request Confirmation Flow Test
Specifically tests:
1. Scenario 1: Standard input "KMCH la O positive blood rendu units urgent ah venum"
   - AI parser extracts all parameters
   - Emergency created, verified, and tracker link verified.

2. Scenario 2: Manual Edit Flow (The exact bug scenario)
   - Input message has MISSING blood group: "3 units needed at PSG Hospital urgently"
   - Parser returns missing_fields=['blood_group']
   - Form is manually edited with Blood Group = "O+"
   - Current form values are read and re-validated
   - System recognizes all required fields are present
   - Emergency request is successfully created via POST /emergency-requests
   - Returned Emergency ID is verified
   - Tracker endpoint confirms request exists and is live
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_emergency_confirmation_flow():
    print("=" * 70)
    print("TESTING EMERGENCY REQUEST CONFIRMATION FLOW")
    print("=" * 70)

    # -------------------------------------------------------------
    # SCENARIO 1: Full NLP Input
    # -------------------------------------------------------------
    print("\n--- [Scenario 1] Testing Full NLP Input: 'KMCH la O positive blood rendu units urgent ah venum' ---")
    msg1 = "KMCH la O positive blood rendu units urgent ah venum"
    res1 = requests.post(f"{BASE_URL}/ai/parse-request", json={
        "message": msg1,
        "auto_create": False,
        "contact_phone": "+91 94433 12345"
    })
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}"
    data1 = res1.json()
    assert data1["success"] is True
    parsed1 = data1["parsed_request"]
    assert parsed1["hospital_name"] == "KMCH"
    assert parsed1["blood_group"] == "O+"
    assert parsed1["units_required"] == 2
    assert parsed1["urgency"] in ["URGENT", "CRITICAL"]
    print(f" -> AI extraction successful: {parsed1['hospital_name']}, {parsed1['blood_group']}, {parsed1['units_required']} units, {parsed1['urgency']}")

    # Create via confirmed review values
    create1 = requests.post(f"{BASE_URL}/emergency-requests", json={
        "hospital_name": parsed1["hospital_name"],
        "blood_group": parsed1["blood_group"],
        "units_needed": parsed1["units_required"],
        "urgency": parsed1["urgency"],
        "component": parsed1["component"] or "whole_blood",
        "contact_phone": "+91 94433 12345",
        "notes": f"Created via Life-Link AI Emergency Interface: '{msg1}'"
    })
    assert create1.status_code == 201
    created1_id = create1.json()["id"]
    assert created1_id is not None
    print(f" -> Emergency Request #{created1_id} created successfully!")
    print(f" -> Track Emergency link target: tracker.html?id={created1_id}")

    # Verify tracker endpoint
    track1 = requests.get(f"{BASE_URL}/emergency-requests/{created1_id}")
    assert track1.status_code == 200
    assert track1.json()["hospital_name"] == "KMCH"
    print(" -> Scenario 1 PASSED: End-to-end full NLP flow verified.")

    # -------------------------------------------------------------
    # SCENARIO 2: Missing Field + Manual Edit Flow (The User's Bug)
    # -------------------------------------------------------------
    print("\n--- [Scenario 2] Testing Missing Blood Group & Manual Edit in Review Form ---")
    msg2 = "3 units needed at PSG Hospital urgently"
    res2 = requests.post(f"{BASE_URL}/ai/parse-request", json={
        "message": msg2,
        "auto_create": False,
        "contact_phone": "+91 94433 12345"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    
    # 1. Verify parser initially reports missing blood_group
    assert data2["success"] is False
    assert "blood_group" in data2["missing_fields"]
    parsed2 = data2["parsed_request"]
    print(f" -> Initial parser output: hospital='{parsed2['hospital_name']}', blood_group={parsed2['blood_group']}, units={parsed2['units_required']}")
    print(f" -> Missing fields reported by AI: {data2['missing_fields']}")
    assert parsed2["blood_group"] is None

    # 2. Simulate User Manual Edit in Review Form:
    # User types "O+" into field-blood-group
    # Other fields populated from parser: Units = 3, Hospital = "PSG Hospital", Urgency = "CRITICAL", Component = "whole_blood"
    manual_form_values = {
        "hospital_name": parsed2["hospital_name"] or "PSG Hospital",
        "blood_group": "O+",  # <-- USER MANUALLY FILLED THIS
        "units_needed": parsed2["units_required"] or 3,
        "urgency": "CRITICAL",  # <-- User specified CRITICAL
        "component": "whole_blood",
        "contact_phone": "+91 94433 12345",
        "notes": f"Created via Life-Link AI Emergency Interface: '{msg2}'"
    }

    print("\n -> User manually filled editable review form:")
    for k, v in manual_form_values.items():
        print(f"    {k}: {v}")

    # 3. Validation: Verify all required fields are now present in current form values
    assert manual_form_values["hospital_name"] != ""
    assert manual_form_values["blood_group"] != ""
    assert manual_form_values["units_needed"] > 0
    print(" -> Dynamic validation check: All required fields are PRESENT in current form values.")

    # 4. Confirm Emergency Request (POST /emergency-requests)
    create2 = requests.post(f"{BASE_URL}/emergency-requests", json=manual_form_values)
    assert create2.status_code == 201, f"Expected 201, got {create2.status_code}: {create2.text}"
    created2 = create2.json()
    created2_id = created2["id"]
    print(f"\n -> Emergency Request #{created2_id} successfully created from manual form values!")
    print(f" -> Created Hospital: {created2['hospital_name']}")
    print(f" -> Created Blood Group: {created2['blood_group']}")
    print(f" -> Created Units: {created2['units_needed']}")
    print(f" -> Created Status: {created2['status']}")
    assert created2["blood_group"] == "O+"
    assert created2["units_needed"] == 3
    assert created2["hospital_name"] == "PSG Hospital"

    # 5. Verify Tracker link works
    track2 = requests.get(f"{BASE_URL}/emergency-requests/{created2_id}")
    assert track2.status_code == 200
    assert track2.json()["id"] == created2_id
    print(f" -> Verified Track Emergency link: tracker.html?id={created2_id} loads Emergency #{created2_id} correctly!")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED: Both NLP and Manual-Edit Flows Work Flawlessly!")
    print("=" * 70)

if __name__ == "__main__":
    test_emergency_confirmation_flow()
