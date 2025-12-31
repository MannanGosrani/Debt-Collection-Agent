from ..state import CallState
from src.utils.llm import classify_intent

def payment_check_node(state: CallState) -> dict:
    user_input = state.get("last_user_input")

    if not user_input:
        return {
            "stage": "payment_check",
            "awaiting_user": True,
        }

    intent = classify_intent(user_input).lower()

    mapping = {
        "paid": "paid",
        "dispute": "disputed",
        "unable": "unable",
        "willing": "willing",
        "callback": "callback",
    }

    payment_status = mapping.get(intent, "unknown")

    return {
        "payment_status": payment_status,
        "stage": "payment_check",
        "awaiting_user": False,
        "last_user_input": None,
    }
