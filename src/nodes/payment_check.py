# src/nodes/payment_check.py

from ..state import CallState
from ..utils.llm import decide_payment_intent


def payment_check_node(state: CallState) -> dict:
    """
    LLM-driven payment intent resolution.

    Responsibilities:
    - Interpret user intent using LLM
    - Mutate state deterministically
    - NEVER infer intent from raw text
    """

    user_input = state.get("last_user_input")

    # --------------------------------------------------
    # Safety: wait for user input
    # --------------------------------------------------
    if not user_input:
        return {
            "stage": "payment_check",
            "awaiting_user": True,
        }

    # --------------------------------------------------
    # Ask LLM to decide intent
    # --------------------------------------------------
    decision = decide_payment_intent(
        user_message=user_input,
        state_snapshot={
            "outstanding_amount": state["outstanding_amount"],
            "days_past_due": state["days_past_due"],
        }
    )

    intent = decision.get("intent")

    # --------------------------------------------------
    # 1️⃣ Happy PTP – agrees to pay now
    # --------------------------------------------------
    if intent == "AGREE_TO_PAY":
        from datetime import datetime
        
        # Extract date from LLM or default to today
        ptp_date = decision.get("date")
        if not ptp_date:
            # Check if user said "today" or similar
            user_lower = user_input.lower()
            if any(word in user_lower for word in ["today", "now", "immediately"]):
                ptp_date = datetime.now().strftime("%d-%m-%Y")
        
        return {
            "payment_status": "willing",
            "pending_ptp_amount": state["outstanding_amount"],
            "pending_ptp_date": ptp_date,
            "awaiting_reason_for_delay": True,
            "awaiting_user": True,
            "stage": "payment_check",
        }

    # --------------------------------------------------
    # 2️⃣ Already Paid
    # --------------------------------------------------
    if intent == "ALREADY_PAID":
        return {
            "payment_status": "paid",
            "awaiting_user": False,  # Let paid_verification_node handle the flow
            "stage": "paid_verification",
        }

    # --------------------------------------------------
    # 3️⃣ Cannot Pay Full – negotiation required
    # --------------------------------------------------
    if intent == "CANNOT_PAY_FULL":
        return {
            "payment_status": "willing",
            "partial_payment_amount": decision.get("can_pay_now"),
            "stage": "negotiation",
            "awaiting_user": False,
        }

    # --------------------------------------------------
    # 4️⃣ Callback / Pay Later
    # --------------------------------------------------
    if intent == "CALLBACK_REQUEST":
        return {
            "payment_status": "callback",
            "awaiting_callback_reason": True,
            "awaiting_user": True,
            "stage": "closing",
        }

    # --------------------------------------------------
    # 5️⃣ Dispute
    # --------------------------------------------------
    if intent == "DISPUTE":
        return {
            "payment_status": "disputed",
            "dispute_reason": user_input,
            "stage": "closing",
            "awaiting_user": False,
        }

    # --------------------------------------------------
    # 6️⃣ Fallback – LLM unsure
    # --------------------------------------------------
    return {
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": (
                "I want to make sure I help you correctly. "
                "Could you please confirm whether you’re able to pay now, "
                "need some time, or have already made the payment?"
            )
        }],
        "awaiting_user": True,
        "stage": "payment_check",
    }