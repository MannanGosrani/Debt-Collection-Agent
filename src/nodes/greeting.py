# src/nodes/greeting.py

from ..state import CallState


def greeting_node(state: CallState) -> dict:
    """
    Initial greeting.
    - Introduces agent
    - Confirms speaking with customer
    - No debt disclosure
    """

    first_name = state["customer_name"].split()[0]

    message = (
        f"Hello {first_name}, good day. "
        f"This is a call from ABC Finance. "
        f"Am I speaking with {state['customer_name']}?"
    )

    return {
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": message
        }],
        "stage": "greeting",
    }
