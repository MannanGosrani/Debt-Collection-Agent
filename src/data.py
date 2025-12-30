

"""
Mock data for debt collection agent.
In production, this would come from CRM APIs.
"""


# Customer database (keyed by phone number)
CUSTOMERS = {
    "+919876543210": {
        "id": "CUST001",
        "name": "Rajesh Kumar",
        "dob": "15-03-1985",  # DD-MM-YYYY
        "phone": "+919876543210",
    },
    "+919876543211": {
        "id": "CUST002",
        "name": "Priya Sharma",
        "dob": "22-07-1990",
        "phone": "+919876543211",
    },
    "+919876543212": {
        "id": "CUST003",
        "name": "Amit Patel",
        "dob": "05-11-1988",
        "phone": "+919876543212",
    },
}


# Loan database (keyed by customer ID)
LOANS = {
    "CUST001": {
        "id": "LN001",
        "type": "Personal Loan",
        "principal": 100000,
        "outstanding": 45000,
        "emi": 5000,
        "due_date": "2024-12-01",
        "days_past_due": 30,
    },
    "CUST002": {
        "id": "LN002",
        "type": "Credit Card",
        "principal": 50000,
        "outstanding": 52500,
        "emi": 0,  # Credit card
        "due_date": "2024-11-15",
        "days_past_due": 45,
    },
    "CUST003": {
        "id": "LN003",
        "type": "Vehicle Loan",
        "principal": 300000,
        "outstanding": 125000,
        "emi": 8500,
        "due_date": "2024-12-10",
        "days_past_due": 20,
    },
}




def get_customer_by_phone(phone: str) -> dict | None:
    """Look up customer by phone number."""
    return CUSTOMERS.get(phone)




def get_loan_by_customer(customer_id: str) -> dict | None:
    """Get loan details for a customer."""
    return LOANS.get(customer_id)




def get_customer_with_loan(phone: str) -> dict | None:
    """Get combined customer and loan info."""
    customer = get_customer_by_phone(phone)
    if not customer:
        return None
    loan = get_loan_by_customer(customer["id"])
    return {"customer": customer, "loan": loan}

# In-memory storage for call outcomes
# (In production, this would be saved to database)
CALL_RECORDS = []
PTP_RECORDS = []
DISPUTE_RECORDS = []




def save_ptp(customer_id: str, amount: float, date: str, plan_type: str) -> str:
    """Save Promise-to-Pay record. Returns PTP ID."""
    ptp_id = f"PTP{len(PTP_RECORDS)+1:04d}"
    PTP_RECORDS.append({
        "id": ptp_id,
        "customer_id": customer_id,
        "amount": amount,
        "date": date,
        "plan_type": plan_type,
    })
    return ptp_id




def save_dispute(customer_id: str, reason: str) -> str:
    """Save dispute record. Returns Dispute ID."""
    dispute_id = f"DSP{len(DISPUTE_RECORDS)+1:04d}"
    DISPUTE_RECORDS.append({
        "id": dispute_id,
        "customer_id": customer_id,
        "reason": reason,
    })
    return dispute_id




def save_call_record(call_summary: dict) -> str:
    """Save call summary. Returns Call ID."""
    call_id = f"CALL{len(CALL_RECORDS)+1:04d}"
    CALL_RECORDS.append({"id": call_id, **call_summary})
    return call_id
