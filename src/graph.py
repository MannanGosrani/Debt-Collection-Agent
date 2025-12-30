# src/graph.py - COMPLETE REWRITE

from langgraph.graph import StateGraph, END
from src.state import CallState

from src.nodes.greeting import greeting_node
from src.nodes.verification import verification_node
from src.nodes.disclosure import disclosure_node
from src.nodes.payment_check import payment_check_node
from src.nodes.negotiation import negotiation_node
from src.nodes.closing import closing_node


def route_next(state: CallState) -> str:
    # Hard stop
    if state.get("is_complete"):
        return END

    # Pause if waiting for user
    if state.get("awaiting_user"):
        return END

    stage = state.get("stage")

    if stage == "init":
        return "greeting"

    if stage == "greeting":
        return "verification"

    if stage == "verification":
        # 🔑 DO NOT re-enter verification once verified
        if state.get("is_verified"):
            return "disclosure"
        return "verification"

    if stage == "verified":
        return "disclosure"

    if stage == "disclosure":
        return "payment_check"

    if stage == "payment_check":
        status = state.get("payment_status")
        if status in ("paid", "disputed"):
            return "closing"
        if status in ("unable", "willing"):
            return "negotiation"
        if status == "callback":
            return "closing"
        return "closing"

    if stage == "negotiation":
        return "closing"

    if stage == "closing":
        return END

    return END


def create_graph():
    graph = StateGraph(CallState)

    # Register all nodes
    graph.add_node("greeting", greeting_node)
    graph.add_node("verification", verification_node)
    graph.add_node("disclosure", disclosure_node)
    graph.add_node("payment_check", payment_check_node)
    graph.add_node("negotiation", negotiation_node)
    graph.add_node("closing", closing_node)

    # Single entry point
    graph.set_entry_point("greeting")

    # Use same routing function for all nodes
    graph.add_conditional_edges(
        "greeting",
        route_next,
        {
            "verification": "verification",
            END: END,
        }
    )

    graph.add_conditional_edges(
        "verification",
        route_next,
        {
            "verification": "verification",
            "disclosure": "disclosure",
            END: END,
        }
    )

    graph.add_conditional_edges(
        "disclosure",
        route_next,
        {
            "payment_check": "payment_check",
            END: END,
        }
    )

    graph.add_conditional_edges(
        "payment_check",
        route_next,
        {
            "negotiation": "negotiation",
            "closing": "closing",
        }
    )

    graph.add_conditional_edges(
        "negotiation",
        route_next,
        {
            "closing": "closing",
        }
    )

    graph.add_edge("closing", END)

    return graph


app = create_graph().compile()