"""
Life-Link Phase 1 Automated Test Script
Tests all Phase 1 endpoints:
1. Root health check
2. Demo data seeding
3. Donor creation
4. Donor retrieval & filtering
5. Emergency request creation
6. Emergency request retrieval
"""

import sys
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_phase1():
    print("=" * 60)
    print("RUNNING LIFE-LINK PHASE 1 VERIFICATION TESTS")
    print("=" * 60)

    # 1. Health check
    print("\n[1/6] Testing Root Health Check ('/')...")
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print(f" -> OK: {res.json()['project']} - Status: {res.json()['status']}")

    # 2. Seed demo data
    print("\n[2/6] Testing Demo Data Seeding ('/seed-demo-data')...")
    res = client.post("/seed-demo-data")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print(f" -> OK: {res.json()}")

    # 3. Create a new donor
    print("\n[3/6] Testing Donor Registration ('POST /donors')...")
    new_donor_payload = {
        "name": "Kavitha Rajan",
        "phone": "+91 99887 76655",
        "blood_group": "B+",
        "city": "Coimbatore (Gandhipuram)",
        "latitude": 11.0183,
        "longitude": 76.9669,
        "availability": "AVAILABLE",
        "donation_type": "whole_blood"
    }
    res = client.post("/donors", json=new_donor_payload)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}"
    donor_data = res.json()
    donor_id = donor_data["id"]
    print(f" -> OK: Created Donor ID {donor_id} ({donor_data['name']} - {donor_data['blood_group']})")

    # 4. Get donors list and filter
    print("\n[4/6] Testing Donor Listing & Filtering ('GET /donors')...")
    res = client.get("/donors")
    assert res.status_code == 200
    all_donors = res.json()
    print(f" -> Total Donors in DB: {len(all_donors)}")
    assert len(all_donors) >= 10

    # Filter by blood group O+
    res_o = client.get("/donors", params={"blood_group": "O+"})
    assert res_o.status_code == 200
    o_donors = res_o.json()
    print(f" -> Total O+ Donors found: {len(o_donors)}")
    assert len(o_donors) > 0, "Should have found O+ donors"
    for d in o_donors[:3]:
        print(f"    - {d['name']} | Blood: {d['blood_group']} | City: {d['city']} | Status: {d['availability']}")

    # 5. Create an emergency request
    print("\n[5/6] Testing Emergency Request Creation ('POST /emergency-requests')...")
    emergency_payload = {
        "patient_name": "Ravi Kumar (Emergency Surgery)",
        "hospital_name": "PSG Hospitals",
        "hospital_city": "Coimbatore",
        "latitude": 11.0245,
        "longitude": 77.0034,
        "resource_type": "blood",
        "component": "whole_blood",
        "blood_group": "O+",
        "units_needed": 2,
        "urgency": "CRITICAL",
        "contact_phone": "+91 98430 55555",
        "notes": "Accident trauma case requiring O+ whole blood immediately."
    }
    res = client.post("/emergency-requests", json=emergency_payload)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}"
    req_data = res.json()
    req_id = req_data["id"]
    print(f" -> OK: Created Emergency Request #{req_id} for {req_data['hospital_name']} (Needed: {req_data['units_needed']} units of {req_data['blood_group']})")

    # 6. Get emergency requests
    print("\n[6/6] Testing Emergency Request Listing ('GET /emergency-requests')...")
    res = client.get("/emergency-requests")
    assert res.status_code == 200
    requests_list = res.json()
    print(f" -> Total Emergency Requests: {len(requests_list)}")
    for r in requests_list:
        print(f"    - Emergency #{r['id']} | Hospital: {r['hospital_name']} | {r['units_needed']} units {r['blood_group']} | Status: {r['status']}")

    print("\n" + "=" * 60)
    print("ALL PHASE 1 TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 60)

if __name__ == "__main__":
    test_phase1()
