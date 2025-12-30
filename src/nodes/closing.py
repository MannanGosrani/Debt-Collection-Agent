# src/nodes/closing.py

from ..state import CallState
from ..data import save_call_record

def closing_node(state: CallState) -> dict:
    """
    End the call professionally and record outcome.
    """

    outcome = state.get("payment_status") or state.get("call_outcome") or "completed"

    summary = f"""
Call completed.
Verified: {state['is_verified']}
Outcome: {outcome}
"""

    call_id = save_call_record({
        "customer_id": state["customer_id"],
        "outcome": outcome,
        "summary": summary.strip()
    })

    closing_message = (
        "Thank you for your time today. "
        "If you have any questions, please feel free to contact us. "
        "Have a good day."
    )

    return {
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": closing_message
        }],
        "call_outcome": outcome,
        "call_summary": summary.strip(),
        "is_complete": True,
        "stage": "closing"
    }
