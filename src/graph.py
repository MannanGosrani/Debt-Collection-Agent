# src/graph.py 

from langgraph.graph import StateGraph, END
from src.state import CallState

from src.nodes.greeting import greeting_node
from src.nodes.verification import verification_node
from src.nodes.disclosure import disclosure_node
from src.nodes.payment_check import payment_check_node
from src.nodes.negotiation import negotiation_node
from src.nodes.closing import closing_node


def should_end(state: CallState) -> str:
    """Check if we should end execution."""
    if state.get("is_complete"):
        return "end"
    if state.get("awaiting_user"):
        return "end"
    return "continue"


def route_from_greeting(state: CallState) -> str:
    """Route after greeting."""
    check = should_end(state)
    if check == "end":
        return END
    return "verification"


def route_from_verification(state: CallState) -> str:
    """Route after verification."""
    check = should_end(state)
    if check == "end":
        return END
    
    # If verified, go to disclosure
    if state.get("is_verified"):
        return "disclosure"
    
    # Not verified yet, stay in verification
    return "verification"


def route_from_disclosure(state: CallState) -> str:
    """Route after disclosure."""
    check = should_end(state)
    if check == "end":
        return END
    
    # Always go to payment_check after disclosure
    return "payment_check"


def route_from_payment_check(state: CallState) -> str:
    """Route after payment check."""
    status = state.get("payment_status")
    
    # Paid, disputed, or callback -> closing
    if status in ("paid", "disputed", "callback"):
        return "closing"
    
    # Unable or willing -> negotiation
    if status in ("unable", "willing", "unknown"):
        return "negotiation"
    
    # Default to closing
    return "closing"


def route_from_negotiation(state: CallState) -> str:
    """Route after negotiation."""
    return "closing"


def create_graph():
    graph = StateGraph(CallState)

    # Register all nodes
    graph.add_node("greeting", greeting_node)
    graph.add_node("verification", verification_node)
    graph.add_node("disclosure", disclosure_node)
    graph.add_node("payment_check", payment_check_node)
    graph.add_node("negotiation", negotiation_node)
    graph.add_node("closing", closing_node)

    # Entry point
    graph.set_entry_point("greeting")

    # Define edges with separate routing functions
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