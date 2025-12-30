# src/nodes/verification.py

from ..state import CallState


def verification_node(state: CallState) -> dict:
    """
    Verify customer identity using DOB.
    Allows max 3 attempts.
    """

    attempts = state["verification_attempts"]
    user_input = state["last_user_input"].lower().strip()
    expected_dob = state["customer_dob"].lower()

    # First attempt: ask DOB
    if attempts == 0:
        return {
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": "For security purposes, could you please confirm your date of birth?"
            }],
            "verification_attempts": 1,
            "stage": "verification",
        }

    # Simple DOB match (refine later if needed)
    dob_match = (
        expected_dob in user_input or
        expected_dob.replace("-", "/") in user_input
    )

    if dob_match:
        return {
            "is_verified": True,
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": "Thank you for confirming your details."
            }],
            "stage": "verification",
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
                    "I'm sorry, I’m unable to verify your identity. "
                    "Please contact our support team for further assistance. Goodbye."
                )
            }],
            "is_complete": True,
            "stage": "closing",
        }

    return {
        "verification_attempts": new_attempts,
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": "That doesn’t match our records. Please confirm your date of birth again."
        }],
        "stage": "verification",
    }
