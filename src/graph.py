# src/graph.py

from langgraph.graph import StateGraph, END
from src.state import CallState

from src.nodes.greeting import greeting_node
from src.nodes.verification import verification_node
from src.nodes.disclosure import disclosure_node
from src.nodes.payment_check import payment_check_node
from src.nodes.negotiation import negotiation_node
from src.nodes.closing import closing_node


def should_continue(state: CallState) -> str:
    """
    Main routing function that determines next step based on current stage.
    """
    stage = state.get("stage")
    is_complete = state.get("is_complete")
    awaiting_user = state.get("awaiting_user")
    
    # If call is complete, end
    if is_complete:
        return END
    
    # If awaiting user input, pause (return END to wait for user)
    if awaiting_user:
        return END
    
    # Route based on stage
    if stage == "init":
        return "greeting"
    
    elif stage == "greeting":
        return "verification"
    
    elif stage == "verification":
        if state.get("is_verified"):
            return "disclosure"
        return "verification"
    
    elif stage == "verified":
        return "disclosure"
    
    elif stage == "disclosure":
        return "payment_check"
    
    elif stage == "payment_check":
        payment_status = state.get("payment_status")
        if payment_status == "willing":
            return "negotiation"
        return "closing"
    
    elif stage == "negotiation":
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            # If last message contains closing phrases, go to closing
            if last_msg.get("role") == "assistant":
                content = last_msg.get("content", "").lower()
                closing_phrases = ["i've documented our discussion", "we'll follow up with you"]
                if any(phrase in content for phrase in closing_phrases):
                    return "closing"
        
        # Otherwise stay in negotiation
        return "negotiation"
    
    elif stage == "closing":
        return END
    
    # Default: end
    return END


def create_graph():
    graph = StateGraph(CallState)

    # Register nodes
    graph.add_node("greeting", greeting_node)
    graph.add_node("verification", verification_node)
    graph.add_node("disclosure", disclosure_node)
    graph.add_node("payment_check", payment_check_node)
    graph.add_node("negotiation", negotiation_node)
    graph.add_node("closing", closing_node)

    # Set conditional edges from each node
    graph.set_conditional_entry_point(
        should_continue,
        {
            "greeting": "greeting",
            "verification": "verification",
            "disclosure": "disclosure",
            "payment_check": "payment_check",
            "negotiation": "negotiation",
            "closing": "closing",
            END: END,
        }
    )
    
    # Each node routes through the same conditional logic
    for node_name in ["greeting", "verification", "disclosure", "payment_check", "negotiation", "closing"]:
        graph.add_conditional_edges(
            node_name,
            should_continue,
            {
                "greeting": "greeting",
                "verification": "verification",
                "disclosure": "disclosure",
                "payment_check": "payment_check",
                "negotiation": "negotiation",
                "closing": "closing",
                END: END,
            }
        )

    return graph


app = create_graph().compile()