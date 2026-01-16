# src/nodes/paid_verification.py - NEW FILE
# Handles "I already paid" claims with verification

from ..state import CallState
from ..utils.llm import generate_ai_response, decide_payment_verification


def paid_verification_node(state: CallState) -> dict:
    """
    When customer claims they already paid, verify with proof.
    
    Flow:
    1. Ask for transaction ID/proof
    2. If has proof -> verify and close
    3. If no proof -> firm warning + route to negotiation
    4. If paid unauthorized -> fraud warning + negotiation
    """
    
    customer_name = state["customer_name"].split()[0]
    user_input = state.get("last_user_input", "")
    messages = state.get("messages", [])
    outstanding = state.get("outstanding_amount", 0)
    days_overdue = state.get("days_past_due", 0)
    
    # 1. Ask for proof (once)
    if not state.get("verification_asked"):
        response = generate_ai_response(
            situation="ask_payment_proof",
            customer_name=customer_name,
            conversation_history=messages,
            outstanding_amount=outstanding,
            days_overdue=days_overdue,
        )
        return {
            "messages": messages + [{"role": "assistant", "content": response}],
            "verification_asked": True,
            "awaiting_user": True,
            "stage": "paid_verification",
        }

    # 2. Wait for user input
    if not user_input:
        return {
            "awaiting_user": True,
            "stage": "paid_verification",
        }

    # 3. LLM decides verification result
    decision = decide_payment_verification(user_input)
    result = decision["verification_result"]

    # 4. Execute decision (NO inference here)
    if result == "HAS_PROOF":
        response = (
            f"Thank you, {customer_name}. "
            f"I'll verify this payment from our side and get back to you shortly. "
            f"You should receive confirmation within 24-48 hours."
        )
        
        return {
            "messages": messages + [{"role": "assistant", "content": response}],
            "payment_status": "paid",
            "is_complete": True,
            "call_outcome": "paid",
            "awaiting_user": False,
            "stage": "closing",
        }

    if result in ["NO_PROOF", "UNAUTHORIZED"]:
        response = generate_ai_response(
            situation="no_proof_firm_warning",
            customer_name=customer_name,
            customer_message=user_input,
            conversation_history=messages,
            outstanding_amount=outstanding,
            days_overdue=days_overdue,
        )
        return {
            "messages": messages + [{"role": "assistant", "content": response}],
            "payment_status": "willing",
            "awaiting_user": True,
            "stage": "paid_verification",
        }

    # UNCLEAR
    response = generate_ai_response(
        situation="handle_verification_response",
        customer_name=customer_name,
        customer_message=user_input,
        conversation_history=messages,
    )

    return {
        "messages": messages + [{"role": "assistant", "content": response}],
        "awaiting_user": True,
        "stage": "paid_verification",
    }