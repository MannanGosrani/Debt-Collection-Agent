from langgraph.graph import StateGraph, END
from src.state import CallState


# =========================
# Routing Functions
# =========================

def route_after_verification(state: CallState) -> str:
    if state["is_verified"]:
        return "disclosure"
    if state["verification_attempts"] >= 3:
        return "closing"
    return "verification"


def route_after_payment_check(state: CallState) -> str:
    status = state.get("payment_status") or "unknown"
    routes = {
        "paid": "already_paid",
        "disputed": "dispute",
        "unable": "negotiation",
        "willing": "ptp_recording",
        "callback": "closing",
    }
    return routes.get(status, "closing")


# =========================
# Graph Factory
# =========================

def create_graph():
    graph = StateGraph(CallState)

    # Register nodes (logic added by teammates)
    graph.add_node("init", lambda s: s)
    graph.add_node("greeting", lambda s: s)
    graph.add_node("verification", lambda s: s)
    graph.add_node("disclosure", lambda s: s)
    graph.add_node("payment_check", lambda s: s)
    graph.add_node("already_paid", lambda s: s)
    graph.add_node("dispute", lambda s: s)
    graph.add_node("negotiation", lambda s: s)
    graph.add_node("ptp_recording", lambda s: s)
    graph.add_node("closing", lambda s: s)

    # Entry point
    graph.set_entry_point("init")

    # Linear flow
    graph.add_edge("init", "greeting")
    graph.add_edge("greeting", "verification")

    # Conditional flows
    graph.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "disclosure": "disclosure",
            "verification": "verification",
            "closing": "closing",
        },
    )

    graph.add_edge("disclosure", "payment_check")

    graph.add_conditional_edges(
        "payment_check",
        route_after_payment_check,
        {
            "already_paid": "already_paid",
            "dispute": "dispute",
            "negotiation": "negotiation",
            "ptp_recording": "ptp_recording",
            "closing": "closing",
        },
    )

    # Terminal paths
    graph.add_edge("already_paid", "closing")
    graph.add_edge("dispute", "closing")
    graph.add_edge("negotiation", "ptp_recording")
    graph.add_edge("ptp_recording", "closing")
    graph.add_edge("closing", END)

    return graph


# Compiled app
app = create_graph().compile()
    