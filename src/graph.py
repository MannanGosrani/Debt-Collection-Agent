# src/graph.py

from langgraph.graph import StateGraph, END
from src.state import CallState

from src.nodes.greeting import greeting_node
from src.nodes.verification import verification_node
from src.nodes.disclosure import disclosure_node
from src.nodes.payment_check import payment_check_node
from src.nodes.paid_verification import paid_verification_node
from src.nodes.negotiation import negotiation_node
from src.nodes.closing import closing_node


def should_continue(state: CallState) -> str:
    """
    Main routing function that determines next step based on current stage.
    """

    stage = state.get("stage")
    is_complete = state.get("is_complete")
    awaiting_user = state.get("awaiting_user")

    # ============================================================
    # 🔒 HARD STOPS
    # ============================================================

    if state.get("session_locked"):
        print("[ROUTING] Session locked, ending")
        return END

    if is_complete:
        return END

    if awaiting_user:
        return END

    # ============================================================
    # ROUTING BY STAGE
    # ============================================================

    if stage == "init":
        return "greeting"

    elif stage == "greeting":
        return "disclosure"

    elif stage == "disclosure":
        return "payment_check"

    elif stage == "payment_check":
        # UPDATED - Lines 70-80: Handle callback mode transitions
        payment_status = state.get("payment_status")

        if state.get("awaiting_reason_for_delay"):
            return END
        
        # NEW: Handle callback mode transitions
        if state.get("callback_mode") == "partial_payment_attempt":
            return END  # Wait for user response

        if payment_status == "paid":
            return "paid_verification"

        if payment_status == "callback":
            return "closing"  # Go directly to closing for escalation

        if payment_status == "willing":
            return "negotiation"

        return "closing"

    elif stage == "paid_verification":
        if state.get("payment_status") == "paid":
            return "closing"
        if state.get("payment_status") == "willing":
            return "negotiation"
        return "closing"

    elif stage == "negotiation":

        # ⛔ BLOCK NEGOTIATION UNTIL USER RESPONDS
        if state.get("awaiting_reason_for_delay"):
            print("[ROUTING] Waiting for delay reason")
            return END

        if state.get("awaiting_whatsapp_confirmation"):
            print("[ROUTING] Waiting for WhatsApp confirmation")
            return END

        if state.get("has_escalated"):
            return "closing"

        if state.get("ptp_id") and state.get("is_complete"):
            return END

        if state.get("ptp_id"):
            return "closing"

        return "negotiation"

    elif stage == "closing":

        if state.get("awaiting_callback_reason"):
            return END

        if state.get("awaiting_escalation_reason"):
            return END

        if state.get("closing_question_asked") and not state.get("is_complete"):
            return "closing"

        return END

    return END


def create_graph():
    graph = StateGraph(CallState)

    graph.add_node("greeting", greeting_node)
    graph.add_node("verification", verification_node)
    graph.add_node("disclosure", disclosure_node)
    graph.add_node("payment_check", payment_check_node)
    graph.add_node("paid_verification", paid_verification_node)
    graph.add_node("negotiation", negotiation_node)
    graph.add_node("closing", closing_node)

    graph.set_conditional_entry_point(
        should_continue,
        {
            "greeting": "greeting",
            "verification": "verification",
            "disclosure": "disclosure",
            "payment_check": "payment_check",
            "paid_verification": "paid_verification",
            "negotiation": "negotiation",
            "closing": "closing",
            END: END,
        }
    )

    for node_name in [
        "greeting",
        "verification",
        "disclosure",
        "payment_check",
        "paid_verification",
        "negotiation",
        "closing",
    ]:
        graph.add_conditional_edges(
            node_name,
            should_continue,
            {
                "greeting": "greeting",
                "verification": "verification",
                "disclosure": "disclosure",
                "payment_check": "payment_check",
                "paid_verification": "paid_verification",
                "negotiation": "negotiation",
                "closing": "closing",
                END: END,
            }
        )

    return graph


app = create_graph().compile()