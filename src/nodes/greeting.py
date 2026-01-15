# src/nodes/greeting.py

from ..state import CallState


def greeting_node(state: CallState) -> dict:
    """
    Initial greeting - professional but still conversational.
    Triggered when customer sends first message.
    """

    # Skip if already greeted
    if state.get("has_greeted"):
        return {
            "stage": "greeting",
            "awaiting_user": False,
        }

    first_name = state["customer_name"].split()[0]
    
    # Check if customer has sent a message first
    messages = state.get("messages", [])
    customer_initiated = False
    
    if messages and messages[-1].get("role") == "user":
        customer_initiated = True
        customer_message = messages[-1].get("content", "").lower()
        print(f"[GREETING] Customer initiated with: '{customer_message}'")

    # Professional greeting - acknowledging their message if they sent one
    if customer_initiated:
        message = (
            f"Hello {first_name}, good day. "
            f"This is ABC Finance reaching out regarding your account. "
            f"Am I speaking with {first_name}?"
        )
    else:
        # Fallback if somehow agent speaks first
        message = (
            f"Hello {first_name}, good day. "
            f"This is ABC Finance reaching out. Am I speaking with {first_name}?"
        )

    return {
        "has_greeted": True,
        "is_verified": True,
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": message
        }],
        "stage": "greeting",
        "awaiting_user": True,
        "last_user_input": None,
    }