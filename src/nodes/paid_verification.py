# src/nodes/paid_verification.py - NEW FILE
# Handles "I already paid" claims with verification

from ..state import CallState
from ..utils.llm import generate_ai_response


def paid_verification_node(state: CallState) -> dict:
    """
    When customer claims they already paid, verify with proof.
    
    Flow:
    1. Ask for transaction ID/proof
    2. If has proof â†’ verify and close
    3. If no proof â†’ firm warning + route to negotiation
    4. If paid unauthorized â†’ fraud warning + negotiation
    """
    
    customer_name = state["customer_name"].split()[0]
    user_input = state.get("last_user_input", "")
    messages = state.get("messages", [])
    outstanding = state.get("outstanding_amount", 0)
    days_overdue = state.get("days_past_due", 0)
    
    # First time - ask for transaction ID
    if not state.get("verification_asked"):
        print("[PAID_VERIFICATION] Asking for transaction proof")
        
        response = generate_ai_response(
            situation="ask_payment_proof",
            customer_name=customer_name,
            customer_message=user_input,
            conversation_history=messages,
            outstanding_amount=outstanding,
            days_overdue=days_overdue,
            context_note=(
                "Customer claims they already paid. ASK for transaction ID or payment receipt. "
                "BE FIRM but professional: Without proof, payment cannot be confirmed. "
                "Keep it conversational but firm."
            )
        )
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "verification_asked": True,
            "stage": "paid_verification",
            "awaiting_user": True,
            "last_user_input": None,
        }
    
    # User has responded - analyze their answer
    if not user_input or user_input.strip() == "":
        return {
            "stage": "paid_verification",
            "awaiting_user": True,
        }
    
    user_lower = user_input.lower()
    
    # Check if they provided something that looks like proof
    has_proof_keywords = any(word in user_lower for word in [
        'transaction', 'txn', 'ref', 'reference', 'utr', 'receipt',
        'confirmation', 'id:', 'number:'
    ])
    
    # Check if they explicitly don't have proof
    no_proof_keywords = any(phrase in user_lower for phrase in [
        "don't have", "dont have", "not with me", "lost it",
        "can't find", "cant find", "didn't get", "didnt get",
        "no receipt", "no proof", "don't know", "dont know"
    ])
    
    # Check if they paid unauthorized person
    unauthorized_payment = any(phrase in user_lower for phrase in [
        "some guy", "someone called", "person called", "agent called",
        "field agent", "collection agent", "guy came"
    ])
    
    # CASE 1: Provided something that looks like proof
    if has_proof_keywords and not no_proof_keywords:
        print("[PAID_VERIFICATION] Customer provided transaction details")
        
        response = generate_ai_response(
            situation="verify_payment_details",
            customer_name=customer_name,
            customer_message=user_input,
            conversation_history=messages,
            outstanding_amount=outstanding,
            context_note=(
                "Customer provided transaction details. Professional response: "
                "Will verify in system. If confirmed, account updated. "
                "If not reflected, customer must pay again. Contact within 24 hours. "
                "Stay firm but fair."
            )
        )
        
        # Route to closing with "paid" status
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "payment_status": "paid",
            "stage": "paid_verification",
            "awaiting_user": False,
            "last_user_input": None,
        }
    
    # CASE 2: No proof OR paid unauthorized person
    elif no_proof_keywords or unauthorized_payment:
        print("[PAID_VERIFICATION] No proof or unauthorized payment - escalating")
        
        # Determine specific scenario
        if unauthorized_payment:
            extra_context = (
                "Customer paid UNAUTHORIZED person. BE VERY FIRM: "
                "(1) Payments to unauthorized persons are NOT valid. "
                "(2) This MAY be fraud - customer should report to police. "
                "(3) Official payments ONLY through our channels. "
            )
        else:
            extra_context = (
                "Customer has NO transaction proof. BE VERY FIRM: "
                "(1) Without official proof, payment is NOT confirmed. "
            )
        
        response = generate_ai_response(
            situation="no_proof_firm_warning",
            customer_name=customer_name,
            customer_message=user_input,
            conversation_history=messages,
            outstanding_amount=outstanding,
            days_overdue=days_overdue,
            context_note=(
                extra_context +
                f"(2) Account REMAINS {days_overdue} days overdue for Rs.{outstanding:,.0f}. "
                f"(3) Late charges Rs.{outstanding * 0.02:,.0f}/day CONTINUE accumulating. "
                f"(4) Credit score being impacted DAILY. "
                f"(5) MUST make official payment immediately. "
                f"Offer to discuss payment options to resolve TODAY. "
                f"Stay professional but apply STRONG pressure."
            )
        )
        
        # Route to negotiation (treat as "willing")
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "payment_status": "willing",  # Route to negotiation
            "stage": "paid_verification",
            "awaiting_user": True,  # Wait for their response
            "last_user_input": None,
        }
    
    # CASE 3: Defensive or unclear response
    else:
        print("[PAID_VERIFICATION] Unclear/defensive response - AI handling")
        
        response = generate_ai_response(
            situation="handle_verification_response",
            customer_name=customer_name,
            customer_message=user_input,
            conversation_history=messages,
            outstanding_amount=outstanding,
            days_overdue=days_overdue,
            context_note=(
                "Customer's response to transaction ID request is unclear or defensive. "
                "UNDERSTAND what they're saying and respond appropriately. "
                "If still no clear proof: Be firm about needing verification. "
                "If defensive/angry: Stay professional but firm. "
                f"Account: {days_overdue} days overdue, Rs.{outstanding:,.0f}. "
                "Ask again for any payment receipt or transaction ID."
            )
        )
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "stage": "paid_verification",
            "awaiting_user": True,
            "last_user_input": None,
        }