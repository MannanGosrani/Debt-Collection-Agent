# src/nodes/payment_check.py

from ..state import CallState
from ..utils.llm import classify_intent

def payment_check_node(state: CallState) -> dict:
    """
    Decide what the customer wants to do regarding payment.
    Uses LLM classification.
    """

    user_input = state["last_user_input"]

    prompt = f"""
Classify the customer's response into ONE category only:

paid       → customer says they already paid
disputed   → customer says loan is wrong / not theirs / incorrect amount
unable     → customer cannot pay right now (financial difficulty)
willing    → customer wants to pay or asks for options
callback   → customer asks to be contacted later

Customer response:
\"\"\"{user_input}\"\"\"

Return ONLY one word.
"""

    intent = classify_intent(prompt).strip().lower()

    valid = ["paid", "disputed", "unable", "willing", "callback"]
    if intent not in valid:
        intent = "unable"  # safe default

    return {
        "payment_status": intent,
        "stage": "payment_check"
    }
