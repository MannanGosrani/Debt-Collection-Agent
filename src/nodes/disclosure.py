# src/nodes/disclosure.py

from ..state import CallState


def disclosure_node(state: CallState) -> dict:
    """
    Text-based disclosure of overdue amount with urgency and consequences.
    Designed for WhatsApp-style messaging (NOT voice-call language).
    """

    # Skip if already disclosed
    if state.get("has_disclosed"):
        return {
            "awaiting_user": False,
        }

    amount = state.get("outstanding_amount", 0)
    loan_type = state.get("loan_type", "loan")
    days_overdue = state.get("days_past_due", 0)
    customer_name = state["customer_name"].split()[0]

    # Estimated late charges (business rule: 2% per day example)
    late_charges = amount * 0.02 * days_overdue

    # Firm, text-based disclosure (NO call framing, NO legal boilerplate)
    message = (
        f"{customer_name}, your {loan_type} account shows an outstanding balance of "
        f"₹{amount:,.0f}, overdue by {days_overdue} days.\n\n"
        f"Important to note:\n"
        f"• Late charges of approximately ₹{late_charges:,.0f} have already been added\n"
        f"• Your total payable amount is increasing daily\n"
        f"• Continued delay will negatively impact your credit profile\n\n"
        f"Immediate payment is the best way to stop further charges.\n"
        f"Can you clear this amount today?"
    )

    return {
        "has_disclosed": True,
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": message
        }],
        "stage": "disclosure",
        "awaiting_user": True,
        "last_user_input": None,
    }
