# src/nodes/payment_check.py

from ..state import CallState
from ..utils.llm import classify_intent
from datetime import datetime


def payment_check_node(state: CallState) -> dict:
    """
    Classify customer's payment intent using Azure-powered classification.
    
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

    # Get the disclosure message (the question that was asked)
    messages = state.get("messages", [])
    disclosure_context = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and ("able to clear this" in msg.get("content", "").lower() or "outstanding amount" in msg.get("content", "").lower()):
            disclosure_context = msg.get("content", "")
            break

    # Classify intent using improved classifier with context
    print(f"\n[PAYMENT_CHECK] Analyzing user input: '{user_input}'")
    intent = classify_intent(user_input, context=disclosure_context).strip().lower()
    print(f"[PAYMENT_CHECK] Classified intent: {intent}\n")

    # Handle "immediate" intent - customer wants to pay full amount today
    if intent == "immediate":
        # Get today's date
        today = datetime.now().strftime("%d-%m-%Y")
        full_amount = state.get("outstanding_amount")
        customer_name = state["customer_name"].split()[0]
        
        # Save PTP for immediate full payment
        from ..data import save_ptp
        ptp_id = save_ptp(
            customer_id=state.get("customer_id"),
            amount=full_amount,
            date=today,
            plan_type="Immediate Full Payment"
        )
        
        print(f"[PAYMENT_CHECK] ✅ Immediate payment commitment - PTP ID: {ptp_id}")
        
        # CRITICAL: Add confirmation message and close conversation
        confirmation_message = (
            f"Excellent, {customer_name}. ✅\n\n"
            f"I've recorded your commitment to pay ₹{full_amount:,.0f} today.\n\n"
            f"Reference Number: PTP{ptp_id}\n\n"
            f"You'll receive payment instructions via SMS within 5 minutes. "
            f"Please complete the payment today as committed."
        )
        
        # Route directly to closing with PTP recorded
        return {
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": confirmation_message
            }],
            "payment_status": "willing",
            "ptp_amount": full_amount,
            "ptp_date": today,
            "ptp_id": ptp_id,
            "call_outcome": "ptp_recorded",
            "stage": "payment_check",  
            "awaiting_user": False,
            "last_user_input": None,
            "is_complete": True,  
        }

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
        print(f"[WARNING] Unexpected payment status: {payment_status}, defaulting to 'willing'")
        payment_status = "willing"

    return {
        "payment_status": payment_status,
        "callback_mode": "reminder" if payment_status == "callback" else None,
        "stage": "payment_check",
        "awaiting_user": False,
        "last_user_input": None,
    }