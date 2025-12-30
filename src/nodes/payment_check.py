# src/nodes/payment_check.py

from ..state import CallState
from ..utils.llm import classify_intent

def payment_check_node(state: CallState) -> dict:
    """
    Decide what the customer wants to do regarding payment.
    Uses LLM classification.
    """

    user_input = state["last_user_input"]

    intent = classify_intent(prompt).strip().lower()

    valid = ["paid", "disputed", "unable", "willing", "callback"]
    if intent not in valid:
        intent = "unable"  # safe default

    return {
        "payment_status": intent,
        "stage": "payment_check"
    }
