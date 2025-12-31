# src/nodes/payment_check.py

from ..state import CallState
from ..utils.llm import classify_intent


def payment_check_node(state: CallState) -> dict:
    """
    Classify customer's payment intent.
    """
    
    user_input = state.get("last_user_input")

    # If no input, wait
    if not user_input or user_input.strip() == "":
        return {
            "stage": "payment_check",
            "awaiting_user": True,
        }

    # Classify intent
    intent = classify_intent(user_input).strip().lower()

    # Map intent to payment status
    mapping = {
        "paid": "paid",
        "dispute": "disputed",
        "disputed": "disputed",
        "unable": "unable",
        "willing": "willing",
        "callback": "callback",
    }

    payment_status = mapping.get(intent, "unable")  # Default to unable

    return {
        "payment_status": payment_status,
        "stage": "payment_check",
        "awaiting_user": False,
        "last_user_input": None,
    }