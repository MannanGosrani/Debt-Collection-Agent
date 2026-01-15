"""
Mock data for debt collection agent.
In production, this would come from CRM APIs.
"""

# Customer database (keyed by phone number)
CUSTOMERS = {
    "+919876543210": {
        "id": "CUST001",
        "name": "Rajesh Kumar",
        "dob": "15-03-1985",
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
    "+917506319945": {
        "id": "CUST004",
        "name": "Mannan Gosrani",
        "dob": "20-07-2004",
        "phone": "+917506319945",
    },
    "+917219559972": {  
        "id": "CUST005",
        "name": "Harshal Kalve",
        "dob": "12-02-1996",
        "phone": "+917219559972",
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
        "emi": 0,
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
    "CUST004": {
        "id": "LN004",
        "type": "Home Loan",
        "principal": 500000,
        "outstanding": 250000,
        "emi": 10000,
        "due_date": "2024-12-15",
        "days_past_due": 15,
    },
    "CUST005": {  
        "id": "LN005",
        "type": "Personal Loan",
        "principal": 150000,
        "outstanding": 60000,
        "emi": 7500,
        "due_date": "2024-12-20",
        "days_past_due": 10,
    },
}



def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number to a standard format for consistent lookups.
    
    Handles:
    - With/without country code (+91 or 91)
    - With/without + prefix
    - Whitespace and special characters
    
    Returns: Phone number with + prefix (e.g., +917506319945)
    """
    if not phone:
        return ""
    
    # Remove all whitespace and special characters except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # If no + prefix, add it
    if not cleaned.startswith('+'):
        # If starts with country code (91 for India), add +
        if cleaned.startswith('91') and len(cleaned) >= 12:
            cleaned = '+' + cleaned
        else:
            # Assume Indian number, add +91
            cleaned = '+91' + cleaned
    
    return cleaned


def get_customer_by_phone(phone: str) -> dict | None:
    """
    Look up customer by phone number.
    Handles various phone number formats through normalization.
    """
    normalized = normalize_phone_number(phone)
    
    # Try exact match first
    if normalized in CUSTOMERS:
        return CUSTOMERS[normalized]
    
    # Try matching by last 10 digits (for Indian numbers)
    # This handles cases where country code might vary
    if len(normalized) >= 10:
        last_10 = normalized[-10:]
        for stored_phone, customer in CUSTOMERS.items():
            if stored_phone.endswith(last_10):
                return customer
    
    return None


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