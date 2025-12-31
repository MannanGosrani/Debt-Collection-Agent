# src/nodes/verification.py

from ..state import CallState


def verification_node(state: CallState) -> dict:
    """
    Verify customer identity using DOB.
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
    expected_dob = state["customer_dob"].lower()

    # First time - ask for DOB
    if attempts == 0:
        return {
            "verification_attempts": 1,
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": "For security purposes, could you please confirm your date of birth?"
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

    user_input = user_input.lower().strip()

    # Check if DOB matches (support multiple formats)
    dob_variations = [
        expected_dob,
        expected_dob.replace("-", "/"),
        expected_dob.replace("-", " "),
    ]
    
    if any(dob in user_input for dob in dob_variations):
        return {
            "is_verified": True,
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": "Thank you for confirming your details."
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

    # Allow retry
    return {
        "verification_attempts": new_attempts,
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": "That doesn't match our records. Please confirm your date of birth again."
        }],
        "stage": "verification",
        "awaiting_user": True,
        "last_user_input": None,
    }