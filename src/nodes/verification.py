# src/nodes/verification.py

from ..state import CallState


def verification_node(state: CallState) -> dict:
    """
    Verify customer identity using DOB.
    Allows max 3 attempts.
    """

    attempts = state["verification_attempts"]
    user_input = state.get("last_user_input", "").lower().strip()
    expected_dob = state["customer_dob"].lower().strip()

    # First attempt: ask DOB
    if attempts == 0:
        return {
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": "For security purposes, could you please confirm your date of birth?"
            }],
            "verification_attempts": 1,
            "stage": "verification",
            "awaiting_user": True,
        }

    # DEBUG: Print what we're comparing
    print(f"\n=== VERIFICATION DEBUG ===")
    print(f"User input: '{user_input}'")
    print(f"Expected DOB: '{expected_dob}'")
    print(f"Attempt: {attempts}")
    
    # Robust DOB matching - try multiple approaches
    # 1. Exact match (with various separators)
    match_1 = expected_dob in user_input
    match_2 = expected_dob.replace("-", "/") in user_input
    match_3 = expected_dob.replace("-", " ") in user_input
    
    # 2. Normalized match (remove all separators)
    user_normalized = user_input.replace("-", "").replace("/", "").replace(" ", "")
    expected_normalized = expected_dob.replace("-", "").replace("/", "").replace(" ", "")
    match_4 = user_normalized == expected_normalized
    
    # 3. Check if user input is exactly the DOB (common case)
    match_5 = user_input == expected_dob
    match_6 = user_input == expected_dob.replace("-", "/")
    
    print(f"Match checks:")
    print(f"  Exact in text: {match_1}")
    print(f"  With / separator: {match_2}")
    print(f"  With space separator: {match_3}")
    print(f"  Normalized: {match_4}")
    print(f"  Exact match: {match_5}")
    print(f"  Exact match /: {match_6}")
    
    dob_match = any([match_1, match_2, match_3, match_4, match_5, match_6])
    print(f"Final result: {dob_match}")
    print(f"=========================\n")

    if dob_match:
        return {
            "is_verified": True,
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": "Thank you for confirming your details."
            }],
            "stage": "verification",
            "awaiting_user": False,
        }

    # Incorrect DOB
    new_attempts = attempts + 1

    if new_attempts >= 3:
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
        }

    return {
        "verification_attempts": new_attempts,
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": "That doesn't match our records. Please confirm your date of birth again."
        }],
        "stage": "verification",
        "awaiting_user": True,
    }