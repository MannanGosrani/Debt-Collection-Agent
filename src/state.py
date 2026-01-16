# src/state.py

from typing import TypedDict, List, Optional, Literal
from src.data import get_customer_with_loan


Stage = Literal[
    "init",
    "greeting",
    "verification",
    "verified",
    "disclosure",
    "payment_check",
    "paid_verification",  # NEW!
    "already_paid",
    "dispute",
    "negotiation",
    "ptp_recording",
    "escalation",
    "closing",
]

PaymentStatus = Literal[
    "paid",
    "disputed",
    "unable",
    "willing",
    "callback",
    "unknown",
]


# =========================
# Call State
# =========================
class CallState(TypedDict):
    # === Conversation ===
    messages: List[dict]
    stage: Stage
    turn_count: int
    last_user_input: Optional[str]
    awaiting_user: bool
    has_greeted: bool
    has_disclosed: bool  
    
    # === Customer Info ===
    customer_id: str
    customer_name: str
    customer_phone: str
    customer_dob: str
    
    # === Loan Info ===
    loan_id: str
    loan_type: str
    outstanding_amount: float
    days_past_due: int
    
    # === Verification ===
    verification_attempts: int
    is_verified: bool
    
    # === Payment Verification ===
    verification_asked: Optional[bool]  # For paid_verification node
    
    # === Interactive Closing ===
    closing_question_asked: Optional[bool]  # For closing node
    
    # === Payment Handling ===
    payment_status: Optional[PaymentStatus]
    
    # === Promise To Pay ===
    ptp_amount: Optional[float]
    ptp_date: Optional[str]
    ptp_id: Optional[str]
    
    # === Dispute ===
    dispute_reason: Optional[str]
    dispute_id: Optional[str]
    
    # === Negotiation ===
    offered_plans: List[dict]
    selected_plan: Optional[dict]
        
    # === Call Outcome ===
    call_outcome: Optional[str]
    call_summary: Optional[str]
    
    # === Flags ===
    is_complete: bool
    
    # === Reason Collection ===
    delay_reason: Optional[str]              # Reason for payment delay
    awaiting_reason_for_delay: Optional[bool]  # Waiting for reason before PTP
    pending_ptp_amount: Optional[float]      # Amount to record after reason
    pending_ptp_date: Optional[str]          # Date to record after reason
    
    callback_reason: Optional[str]           # Why customer needs callback
    awaiting_callback_reason: Optional[bool] # Waiting for callback reason
    callback_reason_collected: Optional[bool]
    
    escalation_reason: Optional[str]         # Why customer refused all options
    awaiting_escalation_reason: Optional[bool]
    escalation_reason_collected: Optional[bool]
      
    # === WhatsApp Confirmation ===
    awaiting_whatsapp_confirmation: Optional[bool]
    
    # === Partial Payment ===
    partial_payment_amount: Optional[float]  # Partial amount customer can pay
    partial_payment_remaining: Optional[float] # Remaining after partial
    awaiting_partial_amount_clarification: Optional[bool]  # NEW - waiting for user to specify amount
    
    # === Negotiation Control (NEW) ===
    offer_stage: int                 # 0 = not started , 1 = immediate settlement warning , 2 = 3-month plan shown , 3 = 6-month plan shown (FINAL)
    refusal_count: int               # Number of times customer refused
    last_offer_made: Optional[str]   # Name of last plan offered
    session_locked: bool             # HARD STOP after WhatsApp confirmation
    has_escalated: bool
    immediate_settlement_stage: int  #  0 (not offered), 1 (first push), 2 (second push with consequences)
    installment_stage: int           #  0 (not offered), 1 (3-month shown), 2 (6-month shown)


# =========================
# Initial State Factory
# =========================
def create_initial_state(phone: str) -> Optional[CallState]:
    """
    Create initial CallState using mock customer + loan data.
    Returns None if customer not found.
    """
    data = get_customer_with_loan(phone)
    if not data:
        return None
    
    customer = data["customer"]
    loan = data["loan"]
    
    state = CallState(
        # Conversation
        messages=[],
        stage="init",
        turn_count=0,
        last_user_input=None,
        awaiting_user=False,
        has_greeted=False,
        has_disclosed=False,
        
        # Customer
        customer_id=customer["id"],
        customer_name=customer["name"],
        customer_phone=customer["phone"],
        customer_dob=customer["dob"],
        
        # Loan
        loan_id=loan["id"],
        loan_type=loan["type"],
        outstanding_amount=loan["outstanding"],
        days_past_due=loan["days_past_due"],
        
        # Verification
        verification_attempts=0,
        is_verified=True,
        
        # Payment Verification
        verification_asked=False,
        
        # Interactive Closing
        closing_question_asked=False,
        
        # Payment
        payment_status=None,
        
        # PTP
        ptp_amount=None,
        ptp_date=None,
        ptp_id=None,
        
        # Dispute
        dispute_reason=None,
        dispute_id=None,
        
        # Negotiation
        offered_plans=[],
        selected_plan=None,
                
        # Outcome
        call_outcome=None,
        call_summary=None,
        
        # Flags
        is_complete=False,
        
        # Reason Collection
        delay_reason=None,
        awaiting_reason_for_delay=False,
        pending_ptp_amount=None,
        pending_ptp_date=None,
        
        callback_reason=None,
        awaiting_callback_reason=False,
        callback_reason_collected=False,
        
        escalation_reason=None,
        awaiting_escalation_reason=False,
        escalation_reason_collected=False,
                
        # WhatsApp Confirmation
        awaiting_whatsapp_confirmation=False,
        
        # Partial Payment
        partial_payment_amount=None,
        partial_payment_remaining=None,
        awaiting_partial_amount_clarification=False,  
        
        # Negotiation Control
        offer_stage=0,
        refusal_count=0,
        last_offer_made=None,
        session_locked=False,
        has_escalated=False,
        immediate_settlement_stage=0,  # NEW: Initialize to 0 (not offered yet)
        installment_stage=0,            # NEW: Initialize to 0 (not offered yet)
    )

    validate_state(state)
    return state


def validate_state(state: CallState):
    """
    Enforces hard invariants on CallState.
    Raises ValueError if state is invalid.
    """

    # If awaiting reason, must be waiting for user input
    # UNLESS we just received input and are about to process it (intermediate state)
    if state.get("awaiting_reason_for_delay"):
        if not state.get("awaiting_user") and not state.get("last_user_input"):
            raise ValueError(
                "Invalid state: awaiting_reason_for_delay=True but awaiting_user=False and no user input"
            )

    if state.get("payment_status") == "willing":
        # Allow partial payment flow without PTP details initially
        if state.get("partial_payment_amount") is not None:
            # Partial payment flow - negotiation in progress, PTP not set yet
            pass
        # Allow when asking for amount clarification
        elif state.get("awaiting_partial_amount_clarification"):
            # Asking user to specify amount - no PTP details needed yet
            pass
        # Allow in negotiation stage without PTP details (NEW)
        elif state.get("stage") == "negotiation" and not state.get("pending_ptp_amount"):
            # In negotiation, still gathering details - allow it
            pass
        # Allow null date if we're still awaiting reason for delay
        elif state.get("awaiting_reason_for_delay"):
            # During reason collection, only amount is required
            if not state.get("pending_ptp_amount"):
                raise ValueError(
                    "Invalid state: awaiting_reason_for_delay without pending_ptp_amount"
                )
        else:
            # After reason collection, both amount and date are required
            if not state.get("pending_ptp_amount") or not state.get("pending_ptp_date"):
                raise ValueError(
                    "Invalid state: payment_status='willing' without pending PTP details"
                )

    # If PTP recorded, core fields must exist
    if state.get("ptp_id"):
        if not state.get("ptp_amount") or not state.get("ptp_date"):
            raise ValueError(
                "Invalid state: ptp_id exists without ptp_amount or ptp_date"
            )

    # If conversation is complete, must have an outcome
    if state.get("is_complete") and not state.get("call_outcome"):
        raise ValueError(
            "Invalid state: is_complete=True without call_outcome"
        )