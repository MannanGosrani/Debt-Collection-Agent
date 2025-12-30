# src/nodes/disclosure.py

from ..state import CallState


def disclosure_node(state: CallState) -> dict:
    """
    Provide legal disclosure and explain outstanding amount.
    """
    
    amount = state.get("outstanding_amount", 0)
    
    message = (
        f"I'm calling regarding your outstanding payment of ₹{amount}. "
        f"This is an attempt to collect a debt. "
        f"Are you able to make this payment today?"
    )
    
    return {
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": message
        }],
        "stage": "disclosure",
        "awaiting_user": True,
    }