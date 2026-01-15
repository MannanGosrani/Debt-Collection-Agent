# src/nodes/payment_check.py

from ..state import CallState
from ..utils.llm import classify_intent
from datetime import datetime


def payment_check_node(state: CallState) -> dict:
    """
    Classify customer's payment intent using Azure-powered classification.
    
    For CALLBACK requests: Ask if they can pay SOME amount now before scheduling callback.
    """

    user_input = state.get("last_user_input")

    # If no input yet, wait for user response
    if not user_input or user_input.strip() == "":
        return {
            "stage": "payment_check",
            "awaiting_user": True,
        }

    # Get the disclosure message context
    messages = state.get("messages", [])
    disclosure_context = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and ("able to clear this" in msg.get("content", "").lower() or "outstanding amount" in msg.get("content", "").lower()):
            disclosure_context = msg.get("content", "")
            break

    # Classify intent
    print(f"\n[PAYMENT_CHECK] Analyzing user input: '{user_input}'")
    intent = classify_intent(user_input, context=disclosure_context).strip().lower()
    print(f"[PAYMENT_CHECK] Classified intent: {intent}\n")

    # Handle "immediate" intent
    if intent == "immediate":
        from datetime import datetime
        today = datetime.now().strftime("%d-%m-%Y")
        full_amount = state.get("outstanding_amount")
        customer_name = state["customer_name"].split()[0]
        
        # Ask for reason before recording PTP
        confirmation_message = (
            f"Excellent, {customer_name}.\n\n"
            f"I'll record your commitment to pay Rs.{full_amount:,.0f} today.\n\n"
            f"Before I finalize this, could you briefly tell me the reason for the payment delay?"
        )
        
        return {
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": confirmation_message
            }],
            "payment_status": "willing",
            "pending_ptp_amount": full_amount,
            "pending_ptp_date": today,
            "selected_plan": {"name": "Immediate Full Payment"},
            "awaiting_reason_for_delay": True,
            "stage": "payment_check",
            "awaiting_user": True,
            "last_user_input": None,
        }

    # Handle "callback" intent - ask if they can pay some amount now
    if intent == "callback":
        customer_name = state["customer_name"].split()[0]
        outstanding = state.get("outstanding_amount", 0)
        days_overdue = state.get("days_past_due", 0)
        
        print("[PAYMENT_CHECK] Callback request - asking for partial payment first")
        
        callback_response = (
            f"{customer_name}, I understand you need time.\n\n"
            f"However, your account is {days_overdue} days overdue for Rs.{outstanding:,.0f}.\n"
            f"Late charges of Rs.{outstanding * 0.02:,.0f} per day are being added.\n\n"
            f"Can you make a partial payment now to minimize further charges? "
            f"Even a partial amount will help reduce the impact on your credit score.\n\n"
            f"How much can you pay today?"
        )
        
        return {
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": callback_response
            }],
            "payment_status": "callback",
            "callback_mode": "partial_payment_attempt",
            "stage": "payment_check",
            "awaiting_user": True,
            "last_user_input": None,
        }

    # Normalize intent
    alias_map = {
        "dispute": "disputed",
        "call_back": "callback",
        "call back": "callback",
    }

    payment_status = alias_map.get(intent, intent)

    # Validate status
    valid_statuses = ["paid", "disputed", "callback", "unable", "willing"]
    if payment_status not in valid_statuses:
        print(f"[WARNING] Unexpected payment status: {payment_status}, defaulting to 'willing'")
        payment_status = "willing"

    return {
        "payment_status": payment_status,
        "stage": "payment_check",
        "awaiting_user": False,
        "last_user_input": None,
    }