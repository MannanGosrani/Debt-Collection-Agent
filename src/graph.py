# src/graph.py

from langgraph.graph import StateGraph, END
from src.state import CallState

from src.nodes.greeting import greeting_node
from src.nodes.verification import verification_node
from src.nodes.disclosure import disclosure_node
from src.nodes.payment_check import payment_check_node
from src.nodes.negotiation import negotiation_node
from src.nodes.closing import closing_node


def route_from_greeting(state: CallState) -> str:
    """Route after greeting"""
    if state.get("is_complete"):
        return END
    if state.get("awaiting_user"):
        return END
    return "verification"


def route_from_verification(state: CallState) -> str:
    """Route after verification"""
    if state.get("is_complete"):
        return END
    if state.get("awaiting_user"):
        return END
    
    # If verified, go to disclosure
    if state.get("is_verified"):
        return "disclosure"
    
    # Stay in verification
    return "verification"


def route_from_disclosure(state: CallState) -> str:
    """Route after disclosure"""
    if state.get("is_complete"):
        return END
    if state.get("awaiting_user"):
        return END
    
    # Always go to payment_check after disclosure
    return "payment_check"


def route_from_payment_check(state: CallState) -> str:
    """Route after payment check"""
    status = state.get("payment_status")
    
    # Paid, disputed, or callback → closing
    if status in ("paid", "disputed", "callback"):
        return "closing"
    
    # Unable or willing → negotiation
    if status in ("unable", "willing", "unknown"):
        return "negotiation"
    
    return "closing"


def route_from_negotiation(state: CallState) -> str:
    """Route after negotiation"""
    return "closing"


def create_graph():
    graph = StateGraph(CallState)

    # Register nodes
    graph.add_node("greeting", greeting_node)
    graph.add_node("verification", verification_node)
    graph.add_node("disclosure", disclosure_node)
    graph.add_node("payment_check", payment_check_node)
    graph.add_node("negotiation", negotiation_node)
    graph.add_node("closing", closing_node)

    # Entry point
    graph.set_entry_point("greeting")

    # Routing
    graph.add_conditional_edges(
        "greeting",
        route_from_greeting,
        {
            "verification": "verification",
            END: END,
        }
    )

    graph.add_conditional_edges(
        "verification",
        route_from_verification,
        {
            "verification": "verification",
            "disclosure": "disclosure",
            END: END,
        }
    )

    graph.add_conditional_edges(
        "disclosure",
        route_from_disclosure,
        {
            "payment_check": "payment_check",
            END: END,
        }
    )

    graph.add_conditional_edges(
        "payment_check",
        route_from_payment_check,
        {
            "negotiation": "negotiation",
            "closing": "closing",
        }
    )

    graph.add_conditional_edges(
        "negotiation",
        route_from_negotiation,
        {
            "closing": "closing",
        }
    )

    graph.add_edge("closing", END)

    return graph


app = create_graph().compile()