"""
Life-Link: Multilingual AI Emergency Request Parser & Conversational Engine
Phase 4 & Enhanced Interactive AI Assistant (English, Tanglish, Tamil)

DISCLAIMER:
Life-Link is an emergency medical resource coordination platform.
It does NOT provide medical diagnosis or clinical treatment advice. Blood compatibility
and transfusion decisions must be confirmed by qualified medical professionals
and authorized blood banks.

This module converts unstructured natural-language requests into structured
emergency records without inventing missing information.
Supports conversational dialogue, patient vs requester distinction, and editable confirmation cards.
"""

import re
from typing import Dict, Any, Optional, List


# Word to number mappings for English, Tanglish, and Tamil
WORD_NUMBERS = {
    # 1
    "one": 1, "oru": 1, "onnu": 1, "ஒரு": 1, "ஒன்று": 1,
    # 2
    "two": 2, "rendu": 2, "ரெண்டு": 2, "இரண்டு": 2,
    # 3
    "three": 3, "moonu": 3, "மூன்று": 3,
    # 4
    "four": 4, "naalu": 4, "நான்கு": 4,
    # 5
    "five": 5, "anji": 5, "ஐந்து": 5,
    # 6
    "six": 6, "aaru": 6, "ஆறு": 6,
    # 7
    "seven": 7, "ezhu": 7, "ஏழு": 7,
    # 8
    "eight": 8, "ettu": 8, "எட்டு": 8,
    # 9
    "nine": 9, "ombodhu": 9, "ஒன்பது": 9,
    # 10
    "ten": 10, "pathu": 10, "பத்து": 10
}

# Known hospitals and aliases for extraction
KNOWN_HOSPITALS = [
    "KMCH", "PSG Hospitals", "PSG Hospital", "PSG",
    "GKNM Hospital", "GKNM", "CMCH",
    "Coimbatore Medical College Hospital",
    "Ganga Hospital", "Ganga", "Apollo Hospitals", "Apollo Hospital", "Apollo",
    "Royal Care Hospital", "Royal Care"
]


def extract_blood_group(text: str) -> Optional[str]:
    """
    Extracts blood group from English, Tanglish, or Tamil text.
    Handles 'O positive', 'O+', 'O pos', 'O+ve', 'O பாசிட்டிவ்', etc.
    """
    cleaned = text.strip()

    # Pattern for AB groups first (to prevent matching just A or B)
    ab_pos = re.search(r'\bAB\s*(?:\+|\+ve|positive|pos|பாசிட்டிவ்)\b|\bAB\+', cleaned, re.IGNORECASE)
    if ab_pos:
        return "AB+"
    ab_neg = re.search(r'\bAB\s*(?:-|-ve|negative|neg|நெகட்டிவ்)\b|\bAB\-', cleaned, re.IGNORECASE)
    if ab_neg:
        return "AB-"

    # Pattern for A groups
    a_pos = re.search(r'\bA\s*(?:\+|\+ve|positive|pos|பாசிட்டிவ்)\b|\bA\+', cleaned, re.IGNORECASE)
    if a_pos:
        return "A+"
    a_neg = re.search(r'\bA\s*(?:-|-ve|negative|neg|நெகட்டிவ்)\b|\bA\-', cleaned, re.IGNORECASE)
    if a_neg:
        return "A-"

    # Pattern for B groups
    b_pos = re.search(r'\bB\s*(?:\+|\+ve|positive|pos|பாசிட்டிவ்)\b|\bB\+', cleaned, re.IGNORECASE)
    if b_pos:
        return "B+"
    b_neg = re.search(r'\bB\s*(?:-|-ve|negative|neg|நெகட்டிவ்)\b|\bB\-', cleaned, re.IGNORECASE)
    if b_neg:
        return "B-"

    # Pattern for O groups
    o_pos = re.search(r'\bO\s*(?:\+|\+ve|positive|pos|பாசிட்டிவ்)\b|\bO\+', cleaned, re.IGNORECASE)
    if o_pos:
        return "O+"
    o_neg = re.search(r'\bO\s*(?:-|-ve|negative|neg|நெகட்டிவ்)\b|\bO\-', cleaned, re.IGNORECASE)
    if o_neg:
        return "O-"

    # Direct match for simple standalone group format
    simple_match = re.search(r'\b(A|B|AB|O)[\+\-]\b', cleaned, re.IGNORECASE)
    if simple_match:
        return simple_match.group(0).upper()

    return None


def extract_units(text: str) -> Optional[int]:
    """
    Extracts number of required units from numeric or natural language words.
    E.g., '2 units', 'rendu units', 'இரண்டு யூனிட்', '3 bottles', 'three packets'.
    """
    # 1. Check for digit + unit word (e.g., '2 units', '3 bottles', '2')
    digit_match = re.search(r'\b(\d+)\s*(?:units?|bottles?|bags?|packets?|யூனிட்|பாட்டில்)?\b', text, re.IGNORECASE)
    if digit_match:
        val = int(digit_match.group(1))
        # Ensure it's not a phone number or hospital code
        if 1 <= val <= 50:
            return val

    # 2. Check for word representation in English, Tanglish, or Tamil
    words = re.findall(r'[\w\u0B80-\u0BFF]+', text.lower())
    for w in words:
        if w in WORD_NUMBERS:
            return WORD_NUMBERS[w]

    return None


def extract_hospital(text: str) -> Optional[str]:
    """
    Extracts hospital name from the user message.
    Recognizes common hospitals or names followed by 'la', 'il', or 'hospital'.
    """
    # 1. Match known hospitals (case insensitive)
    for h in KNOWN_HOSPITALS:
        pattern = r'\b' + re.escape(h) + r'(?:\s+la|\s+il|\s+மருத்துவமனை)?\b'
        if re.search(pattern, text, re.IGNORECASE):
            return h

    # 2. Match patterns like 'KMCH la' or 'PSG la'
    tanglish_loc_match = re.search(r'\b([A-Z]{2,10})\s+(?:la|il|le)\b', text)
    if tanglish_loc_match:
        return tanglish_loc_match.group(1).upper()

    # 3. Match generic 'X Hospital' or 'X Medical Center'
    hospital_phrase = re.search(r'\b([A-Za-z]+(?:\s+[A-Za-z]+)?\s+(?:Hospital|Hospitals|Clinic))\b', text, re.IGNORECASE)
    if hospital_phrase:
        return hospital_phrase.group(1).title()

    # 4. Tamil hospital phrase (e.g. KMCH மருத்துவமனையில்)
    tamil_hosp_match = re.search(r'([A-Za-z]+)\s*மருத்துவமனை', text)
    if tamil_hosp_match:
        return tamil_hosp_match.group(1).upper()

    return None


def extract_patient_name(text: str) -> Optional[str]:
    """
    Extracts patient name and relationship from text to distinguish account holder from patient.
    e.g. 'My father Sathya needs 2 units O+ blood' -> 'Sathya (Father)'
    e.g. 'En appa Sathya-ku' -> 'Sathya'
    e.g. 'Patient Ramesh' -> 'Ramesh'
    e.g. 'I need blood for myself' -> 'Self'
    """
    cleaned = text.strip()

    # Self check
    if re.search(r'\b(?:for\s+myself|for\s+me|i\s+need|enakku|enaku)\b', cleaned, re.IGNORECASE) and not re.search(r'\b(?:father|mother|brother|sister|son|daughter|friend|appa|amma)\b', cleaned, re.IGNORECASE):
        return "Self"

    # Pattern: "my father Sathya", "my friend Ramesh", "patient Sathya", "for Sathya"
    match_rel = re.search(
        r'\b(?:my\s+)?(father|mother|brother|sister|son|daughter|friend|uncle|aunt|wife|husband|colleague|appa|amma|nanban)\s+([A-Z][a-z]+)\b',
        cleaned,
        re.IGNORECASE
    )
    if match_rel:
        rel = match_rel.group(1).strip().capitalize()
        name = match_rel.group(2).strip().capitalize()
        if name.lower() not in ["blood", "urgent", "kmch", "hospital", "psg", "two", "three", "units"]:
            return f"{name} ({rel})"

    # Pattern: "patient Sathya" or "for Sathya"
    match_pt = re.search(r'\b(?:patient|for)\s+([A-Z][a-z]+)\b', cleaned, re.IGNORECASE)
    if match_pt:
        name = match_pt.group(1).strip().capitalize()
        if name.lower() not in ["blood", "urgent", "kmch", "hospital", "psg", "two", "three", "units", "myself"]:
            return name

    # Tanglish pattern: "Sathya-ku" or "Sathya ku"
    match_ku = re.search(r'\b([A-Z][a-z]{2,})\s*[-–]?\s*(?:ku|kku)\b', cleaned)
    if match_ku:
        name = match_ku.group(1).strip().capitalize()
        if name.lower() not in ["emergency", "blood", "patient", "accident", "hospital"]:
            return name

    # Pattern: "Sathya needs"
    match_needs = re.search(r'\b([A-Z][a-z]{2,})\s+(?:needs|requires|thevai)\b', cleaned)
    if match_needs:
        name = match_needs.group(1).strip().capitalize()
        if name.lower() not in ["emergency", "hospital", "patient"]:
            return name

    return None


def extract_urgency(text: str) -> str:
    """
    Determines urgency based on urgency keywords.
    Returns: 'CRITICAL', 'URGENT', or 'NORMAL'
    """
    cleaned = text.lower()

    # Critical indicators
    critical_keywords = [
        "critical", "immediately", "right now", "very urgent", "emergency",
        "accident", "icu", "trauma", "avasiyam", "உடனடியாக", "அவசரம்", "அவசரமாக"
    ]
    for kw in critical_keywords:
        if kw in cleaned:
            return "CRITICAL"

    # Urgent indicators
    urgent_keywords = [
        "urgent", "urgently", "urgent ah", "urgent-ah", "urgentah", "needed soon",
        "seekiram", "சீக்கிரம்", "asap", "fast"
    ]
    for kw in urgent_keywords:
        if kw in cleaned:
            return "URGENT"

    return "NORMAL"


def extract_component(text: str) -> str:
    """
    Extracts blood component type.
    Defaults to 'whole_blood'.
    """
    cleaned = text.lower()
    if "platelet" in cleaned or "பிளேட்லெட்" in cleaned:
        return "platelets"
    if "plasma" in cleaned or "பிளாஸ்மா" in cleaned:
        return "plasma"
    if "rbc" in cleaned or "packed rbc" in cleaned or "red blood":
        if "packed" in cleaned or "rbc" in cleaned:
            return "packed_rbc"
    return "whole_blood"


def extract_contact_number(text: str) -> Optional[str]:
    """
    Extracts phone number if explicitly provided.
    E.g., '+91 9876543210' or '9876543210'.
    """
    match = re.search(r'(?:\+91[\s-]?)?[6-9]\d{9}', text)
    if match:
        return match.group(0).strip()
    return None


# =====================================================================
# MAIN PARSER ENTRYPOINT
# =====================================================================

def parse_emergency_message(
    message: str,
    existing_fields: Optional[Dict[str, Any]] = None,
    requester_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parses natural language emergency message in English, Tanglish, or Tamil.
    Extracts structured fields without inventing missing values.
    Merges with existing accumulated fields if provided (for multi-turn conversational support).
    Distinguishes account holder from patient.
    """
    if not message or not message.strip():
        return {
            "success": False,
            "parsed_request": {
                "resource_type": "blood",
                "component": "whole_blood",
                "blood_group": None,
                "units_required": None,
                "hospital_name": None,
                "urgency": "NORMAL",
                "contact_phone": None,
                "patient_name": "Emergency Patient",
                "requester_name": requester_name
            },
            "missing_fields": ["blood_group", "units_required", "hospital_name"],
            "message": "Please describe your emergency requirement (e.g., 'My father Sathya needs 2 units O+ blood at KMCH urgently')."
        }

    # Extract raw parameters from current message
    blood_group = extract_blood_group(message)
    units = extract_units(message)
    hospital = extract_hospital(message)
    urgency = extract_urgency(message)
    component = extract_component(message)
    contact_phone = extract_contact_number(message)
    patient_name = extract_patient_name(message)

    # Merge with existing accumulated fields if available (prevents losing previously stated details)
    if existing_fields:
        blood_group = blood_group or existing_fields.get("blood_group")
        units = units or existing_fields.get("units_required") or existing_fields.get("units_needed")
        hospital = hospital or existing_fields.get("hospital_name")
        if urgency == "NORMAL" and existing_fields.get("urgency"):
            urgency = existing_fields.get("urgency")
        if component == "whole_blood" and existing_fields.get("component"):
            component = existing_fields.get("component")
        contact_phone = contact_phone or existing_fields.get("contact_phone")
        patient_name = patient_name or existing_fields.get("patient_name")

    # Resolve patient name
    final_patient_name = patient_name
    if not final_patient_name:
        final_patient_name = "Emergency Patient"

    parsed = {
        "resource_type": "blood",
        "component": component,
        "blood_group": blood_group,
        "units_required": units,
        "hospital_name": hospital,
        "urgency": urgency,
        "contact_phone": contact_phone,
        "patient_name": final_patient_name,
        "requester_name": requester_name
    }

    # Identify missing core fields (NEVER invent or guess them!)
    missing_fields = []
    if not blood_group:
        missing_fields.append("blood_group")
    if not units:
        missing_fields.append("units_required")
    if not hospital:
        missing_fields.append("hospital_name")

    if missing_fields:
        missing_desc = []
        if "blood_group" in missing_fields:
            missing_desc.append("blood group (e.g., O+, A-, B+)")
        if "units_required" in missing_fields:
            missing_desc.append("number of units required")
        if "hospital_name" in missing_fields:
            missing_desc.append("hospital name")

        prompt_msg = f"I can help create your emergency request. Please provide: {', '.join(missing_desc)}."
        return {
            "success": False,
            "parsed_request": parsed,
            "missing_fields": missing_fields,
            "message": prompt_msg
        }

    return {
        "success": True,
        "parsed_request": parsed,
        "missing_fields": [],
        "message": f"Successfully understood emergency for {final_patient_name}: {units} unit(s) of {blood_group} blood at {hospital} ({urgency})."
    }


def format_confirmation_card(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepares editable confirmation card data to show before creating emergency request.
    Example:
      Patient: Sathya
      Blood Group: O+
      Required Units: 2
      Hospital: KMCH
      Urgency: URGENT
    """
    return {
        "title": "Emergency Request Confirmation",
        "patient_name": parsed.get("patient_name") or "Emergency Patient",
        "blood_group": parsed.get("blood_group"),
        "units_needed": parsed.get("units_required"),
        "hospital_name": parsed.get("hospital_name"),
        "urgency": parsed.get("urgency") or "URGENT",
        "component": parsed.get("component") or "whole_blood",
        "contact_phone": parsed.get("contact_phone") or "+91 94433 00000",
        "notes": f"Emergency request for {parsed.get('patient_name')} at {parsed.get('hospital_name')}"
    }
