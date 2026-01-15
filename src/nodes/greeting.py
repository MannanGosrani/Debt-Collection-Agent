# src/nodes/greeting.py

from ..state import CallState


def greeting_node(state: CallState) -> dict:
    """
    Initial greeting - professional but still conversational.
    Less emojis, more business-like.
    """

    # Skip if already greeted
    if state.get("has_greeted"):
        return {
            "stage": "greeting",
            "awaiting_user": False,
        }

    first_name = state["customer_name"].split()[0]

    # Professional greeting without excessive friendliness
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