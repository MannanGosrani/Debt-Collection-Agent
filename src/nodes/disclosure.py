# src/nodes/disclosure.py

from ..state import CallState


def disclosure_node(state: CallState) -> dict:
    """
    Provide legal disclosure and explain outstanding amount.
    Only runs once.
    """
    
    # Skip if already disclosed - move to next stage
    if state.get("has_disclosed"):
        return {
            "stage": "payment_check",
            "awaiting_user": False,
        }
    
    amount = state.get("outstanding_amount", 0)
    
    message = (
        f"I'm calling regarding your outstanding payment of ₹{amount}. "
        f"This is an attempt to collect a debt. "
        f"Are you able to make this payment today?"
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