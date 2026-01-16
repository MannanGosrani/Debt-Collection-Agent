# src/graph.py

from langgraph.graph import StateGraph, END
from src.state import CallState

from src.nodes.greeting import greeting_node
from src.nodes.verification import verification_node
from src.nodes.disclosure import disclosure_node
from src.nodes.payment_check import payment_check_node
from src.nodes.paid_verification import paid_verification_node
from src.nodes.negotiation import negotiation_node


def should_continue(state: CallState) -> str:
    stage = state.get("stage")

    if stage == "verified":
        stage = "verification"

    # HARD STOPS
    if state.get("is_complete") or state.get("session_locked"):
        return END

    if state.get("awaiting_user") and stage != "payment_check":
        return END

    if stage == "init":
        return "greeting"

    elif stage == "greeting":
        return "verification"

    elif stage == "verification":
        return "disclosure"

    elif stage == "disclosure":
        return "payment_check"

    elif stage == "payment_check":
        payment_status = state.get("payment_status")

        if payment_status == "paid":
            return "paid_verification"

        if payment_status in ["willing", "callback"]:
            return "negotiation"

        return END

    elif stage == "paid_verification":
        # paid_verification_node controls exit via flags
        if state.get("awaiting_user"):
            return END

        if state.get("payment_status") == "paid":
            return END

        return "negotiation"

    elif stage == "negotiation":
        if state.get("is_complete"):
            return END
        return "negotiation"

    return END


def create_graph():
    graph = StateGraph(CallState)

    # Register nodes
    graph.add_node("greeting", greeting_node)
    graph.add_node("verification", verification_node)
    graph.add_node("disclosure", disclosure_node)
    graph.add_node("payment_check", payment_check_node)
    graph.add_node("paid_verification", paid_verification_node)
    graph.add_node("negotiation", negotiation_node)

    # Entry point
    graph.set_conditional_entry_point(
        should_continue,
        {
            "greeting": "greeting",
            "verification": "verification",
            "disclosure": "disclosure",
            "payment_check": "payment_check",
            "paid_verification": "paid_verification",
            "negotiation": "negotiation",
            END: END,
        }
    )

    # Conditional routing for all nodes
    for node_name in [
        "greeting",
        "verification",
        "disclosure",
        "payment_check",
        "paid_verification",
        "negotiation",
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
                END: END,
            }
        )

    return graph


app = create_graph().compile()
