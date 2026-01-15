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
    
    # === Negotiation Control (NEW) ===
    offer_stage: int                 # 0 = not started , 1 = immediate settlement warning , 2 = 3-month plan shown , 3 = 6-month plan shown (FINAL)
    refusal_count: int               # Number of times customer refused
    last_offer_made: Optional[str]   # Name of last plan offered
    session_locked: bool             # HARD STOP after WhatsApp confirmation
    has_escalated: bool

    
    # === Call Outcome ===
    call_outcome: Optional[str]
    call_summary: Optional[str]
    
    # === Flags ===
    is_complete: bool


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
    
    return CallState(
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
        
        # NEW: Payment Verification
        verification_asked=False,
        
        # NEW: Interactive Closing
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
        
        # Negotiation Control
        offer_stage=0,
        refusal_count=0,
        last_offer_made=None,
        session_locked=False,

        # Outcome
        call_outcome=None,
        call_summary=None,
        
        # Flags
        is_complete=False,
    )