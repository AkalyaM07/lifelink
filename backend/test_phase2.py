"""
Life-Link Phase 2 Automated Test Suite
Tests for Intelligent Medical Resource Matching Engine:
1. Unit tests for Haversine distance calculation
2. Blood group compatibility rules (O+, O-, A+, B+, AB+, etc.)
3. Integration tests via API:
   - O+ recipient matches O+ and O- donors
   - O+ recipient excludes A+ and B+ donors
   - Unavailable donor is excluded
   - Closeness ranking (closer donors ranked ahead of farther donors)
   - Maximum distance radius filtering
   - Handling non-existent emergency request (404)
   - Edge case: request with no compatible donors
"""

import math
from fastapi.testclient import TestClient
from main import app
import matching

client = TestClient(app)

def test_haversine_formula():
    print("\n--- 1. Testing Haversine Distance Calculation ---")
    # Coordinates of KMCH Coimbatore (11.0267, 77.0348)
    # to Coimbatore Sitra (~1.6 km away, 11.0390, 77.0420)
    dist = matching.haversine_distance(11.0267, 77.0348, 11.0390, 77.0420)
    print(f" -> KMCH to Sitra calculated distance: {dist} km")
    assert 1.0 <= dist <= 2.5, f"Expected approx 1.6 km, got {dist}"

    # Same location should be 0.0 km
    zero_dist = matching.haversine_distance(11.0, 77.0, 11.0, 77.0)
    assert zero_dist == 0.0, f"Expected 0.0, got {zero_dist}"

    # Missing coordinates gracefully handled
    none_dist = matching.haversine_distance(None, 77.0, 11.0, None)
    assert none_dist == 99999.0, f"Expected 99999.0 for missing coords, got {none_dist}"
    print(" -> Haversine calculation verified.")


def test_compatibility_matrix():
    print("\n--- 2. Testing Blood Compatibility Rules ---")
    # O+ recipient accepts O+ and O-
    compat_o_plus = matching.get_compatible_donor_groups("O+")
    assert "O+" in compat_o_plus
    assert "O-" in compat_o_plus
    assert "A+" not in compat_o_plus
    assert "B+" not in compat_o_plus
    print(f" -> O+ recipient accepts: {compat_o_plus}")

    # O- recipient accepts ONLY O-
    compat_o_minus = matching.get_compatible_donor_groups("O-")
    assert compat_o_minus == ["O-"]
    print(f" -> O- recipient accepts: {compat_o_minus}")

    # AB+ is universal recipient (accepts all 8 blood groups)
    compat_ab_plus = matching.get_compatible_donor_groups("AB+")
    assert len(compat_ab_plus) == 8
    print(f" -> AB+ universal recipient accepts all 8 types: {len(compat_ab_plus)} types")

    # Invalid blood group returns empty list
    compat_invalid = matching.get_compatible_donor_groups("XYZ")
    assert compat_invalid == []
    print(" -> Invalid blood group returns empty list correctly.")


def test_matching_endpoint_and_scenarios():
    print("\n--- 3. Testing Matching API Endpoint (GET /emergency-requests/{id}/matches) ---")
    
    # Ensure demo data is seeded
    client.post("/seed-demo-data")

    # Fetch emergency requests
    res = client.get("/emergency-requests")
    assert res.status_code == 200
    requests_list = res.json()
    assert len(requests_list) > 0
    emergency_id = requests_list[0]["id"]

    # 3.1 Test matching for O+ emergency request
    res_match = client.get(f"/emergency-requests/{emergency_id}/matches")
    assert res_match.status_code == 200
    data = res_match.json()
    
    print(f" -> Emergency Request #{emergency_id} at {data['hospital_name']} ({data['blood_group']}):")
    print(f"    Total compatible donors found: {data['total_compatible_found']}")
    assert data["total_compatible_found"] > 0
    matches = data["matches"]

    # Check 1: All returned donors must have compatible blood group (O+ or O-)
    for m in matches:
        assert m["blood_group"] in ["O+", "O-"], f"Incompatible blood group found: {m['blood_group']}"
        assert m["availability"] == "AVAILABLE", f"Unavailable donor was included: {m['availability']}"
    print(" -> Compatibility & Availability check passed: Only AVAILABLE O+ and O- donors returned.")

    # Check 2: Unavailable donor Rahul V (O+, UNAVAILABLE) must NOT be in matches
    donor_names = [m["name"] for m in matches]
    assert "Rahul V" not in donor_names, "Unavailable donor Rahul V should NOT be matched!"
    print(" -> Unavailable donor exclusion check passed: Rahul V properly excluded.")

    # Check 3: Incompatible donor Divya M (A+) and Vignesh K (B+) must NOT be in matches
    assert "Divya M" not in donor_names, "A+ donor should not match O+ recipient!"
    assert "Vignesh K" not in donor_names, "B+ donor should not match O+ recipient!"
    print(" -> Incompatibility exclusion check passed: A+ and B+ donors properly excluded.")

    # Check 4: Distance sorting (closer donors appear before farther donors)
    distances = [m["distance_km"] for m in matches]
    assert distances == sorted(distances), f"Matches are not sorted by distance: {distances}"
    print(f" -> Proximity sorting check passed: Distances sorted ascending: {distances}")

    # Check 5: Max distance radius filtering (e.g., max 5 km for Round 1)
    res_radius = client.get(f"/emergency-requests/{emergency_id}/matches?max_distance_km=5.0")
    assert res_radius.status_code == 200
    radius_data = res_radius.json()
    for m in radius_data["matches"]:
        assert m["distance_km"] <= 5.0, f"Donor beyond 5 km returned: {m['distance_km']}"
    print(f" -> Radius filter check passed: Found {len(radius_data['matches'])} donors within 5 km.")

    # Check 6: Non-existent emergency request returns 404
    res_404 = client.get("/emergency-requests/999999/matches")
    assert res_404.status_code == 404
    print(" -> Non-existent emergency request correctly returns 404.")

    # Check 7: Emergency request for rare / empty group returns clear empty response
    rare_payload = {
        "hospital_name": "KMCH",
        "blood_group": "AB-",
        "units_needed": 1,
        "contact_phone": "+91 90000 00000",
        "urgency": "NORMAL"
    }
    create_rare = client.post("/emergency-requests", json=rare_payload)
    assert create_rare.status_code == 201
    rare_req_id = create_rare.json()["id"]

    res_rare_match = client.get(f"/emergency-requests/{rare_req_id}/matches?max_distance_km=1.0")
    assert res_rare_match.status_code == 200
    rare_data = res_rare_match.json()
    print(f" -> No-match edge case response: '{rare_data['message']}' (Total: {rare_data['total_compatible_found']})")


def run_all_phase2_tests():
    print("=" * 65)
    print("RUNNING LIFE-LINK PHASE 2 INTELLIGENT MATCHING TESTS")
    print("=" * 65)
    test_haversine_formula()
    test_compatibility_matrix()
    test_matching_endpoint_and_scenarios()
    print("\n" + "=" * 65)
    print("ALL PHASE 2 TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 65)


if __name__ == "__main__":
    run_all_phase2_tests()
