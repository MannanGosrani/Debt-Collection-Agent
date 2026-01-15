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

    # Check for conversation end requests
    user_lower = user_input.lower().strip()
    end_keywords = [
        "end convo", "end conversation", "end chat", "end call",
        "stop", "exit", "quit",
        "goodbye", "good bye", "bye", "by",
        "i don't want to talk", "don't want to talk", "not interested",
        "leave me alone", "stop calling", "stop messaging"
    ]

    if any(keyword in user_lower for keyword in end_keywords):
        print("[PAYMENT_CHECK] User requested to end conversation")
        customer_name = state["customer_name"].split()[0]
        outstanding = state.get("outstanding_amount", 0)
        days_overdue = state.get("days_past_due", 0)

        response = (
            f"{customer_name}, I understand you wish to end this conversation.\n\n"
            f"However, please be aware:\n"
            f"• Your account remains {days_overdue} days overdue for ₹{outstanding:,.0f}\n"
            f"• Late charges of ₹{outstanding * 0.02:,.0f}/day continue to accumulate\n"
            f"• Your credit score is being impacted daily\n"
            f"• Legal action may be initiated if this remains unresolved\n\n"
            f"This case will be escalated. We strongly recommend making payment as soon as possible."
        )

        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "payment_status": "callback",
            "callback_reason": "Customer requested to end conversation",
            "callback_reason_collected": True,
            "has_escalated": True,
            "stage": "payment_check",
            "awaiting_user": False,
        }

    # Get disclosure context
    messages = state.get("messages", [])
    disclosure_context = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and (
            "able to clear this" in msg.get("content", "").lower()
            or "outstanding amount" in msg.get("content", "").lower()
        ):
            disclosure_context = msg.get("content", "")
            break

    # Classify intent
    print(f"\n[PAYMENT_CHECK] Analyzing user input: '{user_input}'")
    intent = classify_intent(user_input, context=disclosure_context).strip().lower()
    print(f"[PAYMENT_CHECK] Classified intent: {intent}\n")

    # =====================================================
    # IMMEDIATE PAYMENT FLOW
    # =====================================================
    if intent == "immediate":
        today = datetime.now().strftime("%d-%m-%Y")
        full_amount = state.get("outstanding_amount")
        customer_name = state["customer_name"].split()[0]

        confirmation_message = (
            f"Excellent, {customer_name}.\n\n"
            f"I'll record your commitment to pay ₹{full_amount:,.0f} today.\n\n"
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
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
        }

    # =====================================================
    # CALLBACK FLOW (partial payment attempt first)
    # =====================================================
    if intent == "callback":
        customer_name = state["customer_name"].split()[0]
        outstanding = state.get("outstanding_amount", 0)
        days_overdue = state.get("days_past_due", 0)

        if not state.get("callback_mode"):
            callback_response = (
                f"{customer_name}, I understand you need time.\n\n"
                f"However, your account is {days_overdue} days overdue for ₹{outstanding:,.0f}.\n"
                f"Late charges of ₹{outstanding * 0.02:,.0f} per day are being added.\n\n"
                f"Can you make a partial payment now to minimize further charges?\n\n"
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

        return {
            "payment_status": "callback",
            "stage": "closing",
            "awaiting_user": False,
        }

    # Map intent to payment status
    intent_to_status = {
        "immediate": "willing",
        "paid": "paid",
        "disputed": "disputed",
        "callback": "callback",
        "unable": "unable",
        "willing": "willing",
    }

    # Get payment status from intent mapping
    payment_status = intent_to_status.get(intent, "willing")

    # Validate status (just for safety)
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
