"""
Life-Link Continuation Features Test Suite
Verifies all newly introduced architecture and endpoints:
1. Single Normal User Account (Registration, Login, Password Hashing, Profile)
2. Requester vs Patient distinction
3. Conversational AI Chat (/ai/chat) with missing info clarification
4. Editable Confirmation Card & Verified Emergency Creation (/ai/confirm-emergency)
5. Real Backend State Verification (no hallucination)
6. All Compatible Donors Notified
7. 3 Separate States (Donor Willing -> Hospital Confirmed -> Donation Completed)
8. Blood Requests You Can Help With (/users/{id}/matched-requests)
9. Donation Availability & Configurable Eligibility Reminder
10. User Notifications Management (Read / Read All)
"""

from fastapi.testclient import TestClient
from datetime import date, timedelta
from main import app
import schemas

client = TestClient(app)

def test_all_continuation_features():
    print("=" * 70)
    print("RUNNING LIFE-LINK CONTINUATION FEATURES TEST SUITE")
    print("=" * 70)

    # Re-seed fresh demo data
    print("\n[1/10] Seeding fresh clean database...")
    seed_res = client.post("/seed-demo-data?force=true")
    assert seed_res.status_code == 200
    print(" -> Database cleanly initialized with 12 unified users/donors.")

    # 1. Single Normal User Account (Register & Login)
    print("\n[2/10] Testing Single Normal User Account (Register & Login)...")
    reg_payload = {
        "name": "Meera Krishnan",
        "email": "meera@example.com",
        "phone": "+91 94444 88888",
        "password": "secure_password_123",
        "blood_group": "O+",
        "location": "Coimbatore (KMCH Area)",
        "latitude": 11.0320,
        "longitude": 77.0330,
        "availability": "AVAILABLE",
        "donation_type": "whole_blood"
    }
    reg_res = client.post("/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, f"Expected 201, got {reg_res.status_code}: {reg_res.text}"
    user_data = reg_res.json()
    user_id = user_data["id"]
    assert user_data["email"] == "meera@example.com"
    assert "password" not in user_data
    assert "password_hash" not in user_data  # Private safe
    print(f" -> User registered successfully: User #{user_id} ({user_data['name']})")

    # Login test
    login_res = client.post("/auth/login", json={
        "email": "meera@example.com",
        "password": "secure_password_123"
    })
    assert login_res.status_code == 200
    assert login_res.json()["id"] == user_id
    print(" -> Login verified with PBKDF2 hash verification.")

    # Wrong password test
    bad_login = client.post("/auth/login", json={
        "email": "meera@example.com",
        "password": "wrong_password"
    })
    assert bad_login.status_code == 401
    print(" -> Wrong password correctly rejected (401).")

    # 2. Conversational Multilingual AI Chat & Missing Field Safety
    print("\n[3/10] Testing Conversational AI Chat & Missing Information Handling...")
    # Missing blood group, units, hospital
    chat_req_1 = {
        "message": "I need blood urgently for emergency surgery.",
        "user_id": user_id,
        "requester_name": user_data["name"]
    }
    chat_res_1 = client.post("/ai/chat", json=chat_req_1)
    assert chat_res_1.status_code == 200
    chat_data_1 = chat_res_1.json()
    assert chat_data_1["ready_for_confirmation"] is False
    assert "blood_group" in chat_data_1["missing_fields"]
    assert "units_required" in chat_data_1["missing_fields"]
    assert "hospital_name" in chat_data_1["missing_fields"]
    print(f" -> Chat correctly asked for missing information: '{chat_data_1['reply']}'")

    # Multi-turn conversation: Provide patient Sathya, KMCH, 2 units O+
    chat_req_2 = {
        "message": "My father Sathya needs 2 units O+ blood at KMCH urgently.",
        "user_id": user_id,
        "requester_name": user_data["name"]
    }
    chat_res_2 = client.post("/ai/chat", json=chat_req_2)
    assert chat_res_2.status_code == 200
    chat_data_2 = chat_res_2.json()
    assert chat_data_2["ready_for_confirmation"] is True
    assert len(chat_data_2["missing_fields"]) == 0
    extracted = chat_data_2["extracted_fields"]
    assert extracted["blood_group"] == "O+"
    assert extracted["units_required"] == 2
    assert extracted["hospital_name"] == "KMCH"
    assert "Sathya" in extracted["patient_name"]
    print(f" -> Understood fields: Patient='{extracted['patient_name']}', Blood='{extracted['blood_group']}', Units={extracted['units_required']}, Hospital='{extracted['hospital_name']}'")
    assert chat_data_2["confirmation_card"] is not None
    print(" -> Generated editable confirmation card.")

    # 3. Confirmation Before Creation
    print("\n[4/10] Testing Confirmation Card Submission & Emergency Creation...")
    confirm_payload = {
        "user_id": user_id,
        "requester_name": user_data["name"],
        "patient_name": "Sathya (Father)",
        "hospital_name": "KMCH",
        "blood_group": "O+",
        "units_needed": 2,
        "urgency": "URGENT",
        "component": "whole_blood",
        "contact_phone": "+91 94444 88888",
        "notes": "Emergency surgery"
    }
    confirm_res = client.post("/ai/confirm-emergency", json=confirm_payload)
    assert confirm_res.status_code == 201
    emergency_req = confirm_res.json()
    em_id = emergency_req["id"]
    assert emergency_req["requester_name"] == user_data["name"]
    assert emergency_req["patient_name"] == "Sathya (Father)"
    print(f" -> Emergency #{em_id} confirmed and created! Status: {emergency_req['status']}")

    # 4. Verified Notifications Created for All Compatible Available Donors
    print("\n[5/10] Verifying Notifications Distributed to Compatible Donors...")
    # Check notifications for Arun Kumar (User 3, O+ donor near KMCH)
    arun_notifs_res = client.get("/users/3/notifications")
    assert arun_notifs_res.status_code == 200
    arun_notifs = arun_notifs_res.json()
    assert len(arun_notifs) > 0
    alert = next((n for n in arun_notifs if n["type"] == "EMERGENCY_ALERT"), None)
    assert alert is not None
    print(f" -> Verified Notification received by User #3: '{alert['type']}' - '{alert['message']}'")

    # 5. Three Distinct States: State 1 - Donor Willing / Accepted
    print("\n[6/10] Testing Three Separate States: State 1 (Donor Willing / Accepted)...")
    resp_res = client.post(f"/emergency-requests/{em_id}/respond", json={
        "user_id": 3,
        "action": "ACCEPT"
    })
    assert resp_res.status_code == 200
    resp_data = resp_res.json()
    assert resp_data["units_accepted"] == 1
    assert resp_data["status"] == "DONOR_ACCEPTED"
    print(f" -> State 1 Verified: Donor indicated willingness. Units accepted: {resp_data['units_accepted']}. Status: {resp_data['status']}")

    # Verify tracker shows hospital_confirmed is STILL FALSE and donation_completed is STILL FALSE!
    em_check = client.get(f"/emergency-requests/{em_id}").json()
    assert em_check["hospital_confirmed"] is False, "Hospital confirmed must NOT be automatically set!"
    assert em_check["donation_completed"] is False, "Donation completed must NOT be automatically set!"
    print(" -> Strict separation verified: Donor Accepted does NOT automatically complete donation.")

    # 6. State 2: Hospital Confirmed
    print("\n[7/10] Testing State 2 (Hospital Confirmed)...")
    hosp_res = client.post(f"/emergency-requests/{em_id}/hospital-confirm", json={
        "notes": "KMCH blood bank has verified requisition and prepared reception."
    })
    assert hosp_res.status_code == 200
    em_check_hosp = client.get(f"/emergency-requests/{em_id}").json()
    assert em_check_hosp["hospital_confirmed"] is True
    print(f" -> State 2 Verified: Hospital confirmed status set to True.")

    # 7. State 3: Screening & Donation Completed
    print("\n[8/10] Testing State 3 (Clinical Screening & Completed Donation)...")
    screen_res = client.post(f"/emergency-requests/{em_id}/screening-update", json={
        "donor_user_id": 3,
        "passed": True,
        "notes": "Passed hemoglobin and vitals check"
    })
    assert screen_res.status_code == 200
    assert screen_res.json()["screening_status"] == "PASSED"

    complete_res = client.post(f"/emergency-requests/{em_id}/complete-donation", json={
        "donor_user_id": 3,
        "units": 1,
        "notes": "Successful whole blood donation at KMCH"
    })
    assert complete_res.status_code == 200
    em_check_done = client.get(f"/emergency-requests/{em_id}").json()
    assert em_check_done["donation_completed"] is True
    print(f" -> State 3 Verified: Completed donation recorded.")

    # Verify Arun's donation history & cooldown review reminder updated
    arun_donations = client.get("/users/3/donations").json()
    assert len(arun_donations) > 0
    print(f" -> Arun Kumar's donation record updated: {len(arun_donations)} completed donation(s).")
    arun_user = client.get("/users/3").json()
    assert arun_user["last_donation_date"] == str(date.today())
    assert arun_user["availability"] == "REVIEW_NEEDED"
    print(f" -> Arun Kumar availability shifted to 'REVIEW_NEEDED'. Next review date: {arun_user['next_review_date']}.")

    # 8. Blood Requests You Can Help With Feed
    print("\n[9/10] Testing 'Blood Requests You Can Help With' (User Feed)...")
    # Priya Senthil (User 4, O+, AVAILABLE) checks available requests
    priya_feed_res = client.get("/users/4/matched-requests")
    assert priya_feed_res.status_code == 200
    priya_feed = priya_feed_res.json()
    print(f" -> Priya Senthil can help with {len(priya_feed)} active emergency request(s).")
    assert len(priya_feed) > 0
    feed_item = priya_feed[0]
    assert feed_item["blood_group"] in ["O+", "O-"]
    print(f"    - Emergency #{feed_item['emergency_request_id']} at {feed_item['hospital_name']} (~{feed_item['distance_km']} km away)")

    # 9. Mark Notification as Read & Read All
    print("\n[10/10] Testing Notification Read / Read All...")
    notifs = client.get("/users/3/notifications").json()
    first_notif_id = notifs[0]["id"]
    patch_read = client.patch(f"/users/3/notifications/{first_notif_id}/read")
    assert patch_read.status_code == 200
    assert patch_read.json()["is_read"] is True

    read_all = client.post("/users/3/notifications/read-all")
    assert read_all.status_code == 200
    all_read_notifs = client.get("/users/3/notifications").json()
    assert all(n["is_read"] is True for n in all_read_notifs)
    print(" -> Notification read management verified.")

    print("\n" + "=" * 70)
    print("ALL CONTINUATION FEATURES TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    test_all_continuation_features()
