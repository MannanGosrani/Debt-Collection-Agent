# src/nodes/verification.py

from ..state import CallState
import re


def normalize_dob_input(user_input: str, expected_dob: str) -> bool:
    """
    Check if user DOB input matches expected DOB.
    Handles multiple formats:
    - DD-MM-YYYY, DD/MM/YYYY, DD MM YYYY
    - "22nd July 1990", "July 22 1990", "22nd of July 1990"
    - "July 22, 1990" (US format)
    - Partial dates without year: "22nd July", "22-07"
    
    Args:
        user_input: User's DOB input
        expected_dob: Expected DOB in DD-MM-YYYY format (e.g., "22-07-1990")
    
    Returns:
        True if match, False otherwise
    """
    
    user_lower = user_input.lower().strip()
    expected_day, expected_month, expected_year = expected_dob.split('-')
    
    # Month name mapping (both short and full forms)
    months_map = {
        'jan': '01', 'january': '01',
        'feb': '02', 'february': '02',
        'mar': '03', 'march': '03',
        'apr': '04', 'april': '04',
        'may': '05',
        'jun': '06', 'june': '06',
        'jul': '07', 'july': '07',
        'aug': '08', 'august': '08',
        'sep': '09', 'september': '09',
        'oct': '10', 'october': '10',
        'nov': '11', 'november': '11',
        'dec': '12', 'december': '12',
    }
    
    # PRIORITY 1: Check for month names (handles natural language dates)
    for month_name, month_num in months_map.items():
        if month_name in user_lower:
            # Only proceed if this is the expected month
            if month_num != expected_month:
                continue
            
            # Pattern 1: "22nd July 1990" or "22nd of July 1990"
            # Day comes BEFORE month
            pattern1 = rf'(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{month_name}'
            match1 = re.search(pattern1, user_lower)
            
            # Pattern 2: "July 22 1990" or "July 22, 1990"
            # Day comes AFTER month
            pattern2 = rf'{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?'
            match2 = re.search(pattern2, user_lower)
            
            day_match = match1 or match2
            
            if day_match:
                day = day_match.group(1).zfill(2)
                
                # Extract year (if present)
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', user_lower)
                year = year_match.group(0) if year_match else None
                
                # Validate day
                if day == expected_day:
                    # If year provided, must match; if not provided, still accept
                    if year is None or year == expected_year:
                        print(f"[VERIFICATION] ✅ Matched natural language: '{user_input}'")
                        return True
    
    # PRIORITY 2: Check for standard numeric formats
    # DD-MM-YYYY, DD/MM/YYYY, DD MM YYYY
    standard_formats = [
        expected_dob,                           # 22-07-1990
        expected_dob.replace("-", "/"),         # 22/07/1990
        expected_dob.replace("-", " "),         # 22 07 1990
    ]
    
    for format_variant in standard_formats:
        if format_variant in user_lower:
            print(f"[VERIFICATION] ✅ Matched standard format: '{user_input}'")
            return True
    
    # PRIORITY 3: Check for partial match (DD-MM without year)
    partial_match = f"{expected_day}-{expected_month}"
    partial_variations = [
        partial_match,                          # 22-07
        partial_match.replace("-", "/"),        # 22/07
        partial_match.replace("-", " "),        # 22 07
    ]
    
    for partial_variant in partial_variations:
        if partial_variant in user_lower:
            print(f"[VERIFICATION] ✅ Matched partial date: '{user_input}'")
            return True
    
    # PRIORITY 4: Handle US format "MM/DD/YYYY" or "Month DD, YYYY"
    # Convert expected DD-MM-YYYY to MM-DD-YYYY
    us_format = f"{expected_month}-{expected_day}-{expected_year}"
    us_variations = [
        us_format.replace("-", "/"),            # 07/22/1990
        us_format.replace("-", " "),            # 07 22 1990
    ]
    
    for us_variant in us_variations:
        if us_variant in user_lower:
            print(f"[VERIFICATION] ✅ Matched US format: '{user_input}'")
            return True
    
    print(f"[VERIFICATION] ❌ No match for: '{user_input}'")
    return False


def verification_node(state: CallState) -> dict:
    """
    Verify customer identity using DOB - conversational style.
    Allows max 3 attempts.
    """

    # Skip if already verified
    if state.get("is_verified"):
        return {
            "stage": "verified",
            "awaiting_user": False,
        }

    attempts = state.get("verification_attempts", 0)
    user_input = state.get("last_user_input")
    expected_dob = state["customer_dob"]

    # First time - ask for DOB (friendly, not robotic)
    if attempts == 0:
        return {
            "verification_attempts": 1,
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": (
                    "For security purposes, could you please confirm your date of birth?"
                )
            }],
            "stage": "verification",
            "awaiting_user": True,
            "last_user_input": None,
        }

    # If no user input yet, wait
    if not user_input or user_input.strip() == "":
        return {
            "stage": "verification",
            "awaiting_user": True,
        }

    # Check if DOB matches using improved normalization
    if normalize_dob_input(user_input, expected_dob):
        return {
            "is_verified": True,
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": "Great, thanks for confirming! ✅"
            }],
            "stage": "verified",
            "awaiting_user": False,
            "last_user_input": None,
        }

    # Incorrect DOB
    new_attempts = attempts + 1

    # Max attempts reached (>= 4 means 3 failed attempts)
    if new_attempts >= 4:
        return {
            "verification_attempts": new_attempts,
            "is_verified": False,
            "call_outcome": "verification_failed",
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": (
                    "I'm sorry, I'm unable to verify your identity. "
                    "Please contact our support team for further assistance. Goodbye."
                )
            }],
            "is_complete": True,
            "stage": "closing",
            "awaiting_user": False,
            "last_user_input": None,
        }

    # Allow retry (friendly tone)
    return {
        "verification_attempts": new_attempts,
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": (
                "That doesn't match our records. Please confirm your date of birth again."
            )
        }],
        "stage": "verification",
        "awaiting_user": True,
        "last_user_input": None,
    }