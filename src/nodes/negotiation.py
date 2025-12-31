# src/nodes/negotiation.py

from ..state import CallState
from ..utils.llm import generate_response


def negotiation_node(state: CallState) -> dict:
    """
    Offer payment plans when customer cannot pay immediately.
    """

    amount = state["outstanding_amount"]

    prompt = f"""
You are a debt collection agent on a voice call.
Customer cannot pay immediately.

Outstanding amount: ₹{amount}

Politely offer 2-3 payment options, for example:
- Partial payment now
- EMI plan
- Pay full amount on a later date

Keep response short and professional.
"""

    response = generate_response(prompt)

    offered_plans = [
        {"type": "partial", "description": "Partial now, rest later"},
        {"type": "emi", "description": "Monthly installment plan"},
        {"type": "later", "description": "Full payment on a future date"},
    ]

    return {
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": response
        }],
        "offered_plans": offered_plans,
        "stage": "negotiation",
        "awaiting_user": False,
        "last_user_input": None,
    }