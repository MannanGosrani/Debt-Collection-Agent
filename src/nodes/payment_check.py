# src/nodes/payment_check.py

from ..state import CallState
from ..utils.llm import classify_intent


def payment_check_node(state: CallState) -> dict:
    """
    Classify customer's payment intent using Gemini-powered classification.
    
    This node determines the customer's response to the debt disclosure
    and routes them to the appropriate next step.
    """

    user_input = state.get("last_user_input")

    # If no input yet, wait for user response
    if not user_input or user_input.strip() == "":
        return {
            "stage": "payment_check",
            "awaiting_user": True,
        }

    # Classify intent using improved Gemini-based classifier
    print(f"\n[PAYMENT_CHECK] Analyzing user input: '{user_input}'")
    intent = classify_intent(user_input).strip().lower()
    print(f"[PAYMENT_CHECK] Classified intent: {intent}\n")

    # Normalize any spelling variations (just in case)
    alias_map = {
        "dispute": "disputed",
        "call_back": "callback",
        "call back": "callback",
    }

    payment_status = alias_map.get(intent, intent)

    # Validate that we got a valid status
    valid_statuses = ["paid", "disputed", "callback", "unable", "willing"]
    if payment_status not in valid_statuses:
        print(f"[WARNING] Unexpected payment status: {payment_status}, defaulting to 'unable'")
        payment_status = "unable"

    return {
        "payment_status": payment_status,
        "stage": "payment_check",
        "awaiting_user": False,
        "last_user_input": None,
    }