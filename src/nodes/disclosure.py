# src/nodes/disclosure.py

from ..state import CallState


def disclosure_node(state: CallState) -> dict:
    """
    Provide legal disclosure and explain outstanding amount.
    Only runs once.
    """
    
    # Skip if already disclosed - but don't change stage
    if state.get("has_disclosed"):
        return {
            "awaiting_user": False,  # Don't wait again, move on
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
        "stage": "disclosure",  # Set stage to disclosure
        "awaiting_user": True,
        "last_user_input": None,  
    }