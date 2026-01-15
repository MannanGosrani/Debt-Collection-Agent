# src/graph.py

from langgraph.graph import StateGraph, END
from src.state import CallState

from src.nodes.greeting import greeting_node
from src.nodes.verification import verification_node
from src.nodes.disclosure import disclosure_node
from src.nodes.payment_check import payment_check_node
from src.nodes.paid_verification import paid_verification_node  # NEW!
from src.nodes.negotiation import negotiation_node
from src.nodes.closing import closing_node


def should_continue(state: CallState) -> str:
    """
    Main routing function that determines next step based on current stage.
    """
    
    #  HARD STOP AFTER ESCALATION
    if state.get("stage") == "escalation":
        print("[ROUTING] Escalation reached — ending conversation")
        return END
    
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
        return "disclosure"
        
    elif stage == "disclosure":
        return "payment_check"
    
    elif stage == "payment_check":
        payment_status = state.get("payment_status")
        
        # CRITICAL: If immediate payment was recorded AND marked complete, end
        if state.get("is_complete") and state.get("ptp_id"):
            print("[ROUTING] Immediate payment recorded and complete, ending")
            return END
        
        # CRITICAL: If immediate payment was recorded (PTP exists), go directly to closing
        if state.get("ptp_id") and payment_status == "willing":
            print("[ROUTING] Immediate PTP recorded, going to closing")
            return "closing"
               
        # NEW: If customer claims paid, verify first
        if payment_status == "paid":
            print("[ROUTING] Paid claim, going to paid_verification")
            return "paid_verification"
        
        # If customer wants to negotiate, go to negotiation
        if payment_status == "willing":
            print("[ROUTING] Willing, going to negotiation")
            return "negotiation"
        
        # All other statuses (disputed, callback, unable) go to closing
        print(f"[ROUTING] {payment_status}, going to closing")
        return "closing"
    
    elif stage == "paid_verification":
        # After verification, route based on updated payment_status
        payment_status = state.get("payment_status")
        
        if payment_status == "paid":
            # Verified or at least acknowledged
            print("[ROUTING] Verification done, going to closing")
            return "closing"
        elif payment_status == "willing":
            # No proof, route to negotiation
            print("[ROUTING] No proof, going to negotiation")
            return "negotiation"
        
        # Fallback
        return "closing"
    
    elif stage == "negotiation":
        # Check if PTP saved
        if state.get("ptp_id"):
            print("[ROUTING] PTP saved in negotiation, going to closing")
            return "closing"
        
        # Check for closing signals
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if last_msg.get("role") == "assistant":
                content = last_msg.get("content", "").lower()
                closing_phrases = ["i've documented our discussion", "we'll follow up with you"]
                if any(phrase in content for phrase in closing_phrases):
                    print("[ROUTING] Closing phrase detected, going to closing")
                    return "closing"
        
        # Stay in negotiation
        return "negotiation"
    
    elif stage == "closing":
        # Check if asking question and waiting for response
        if state.get("closing_question_asked") and not state.get("is_complete"):
            print("[ROUTING] Closing question asked, staying in closing")
            return "closing"
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
    graph.add_node("paid_verification", paid_verification_node)  # NEW!
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
            "paid_verification": "paid_verification",  # NEW!
            "negotiation": "negotiation",
            "closing": "closing",
            END: END,
        }
    )
    
    # Each node routes through the same conditional logic
    for node_name in ["greeting", "verification", "disclosure", "payment_check", "paid_verification", "negotiation", "closing"]:
        graph.add_conditional_edges(
            node_name,
            should_continue,
            {
                "greeting": "greeting",
                "verification": "verification",
                "disclosure": "disclosure",
                "payment_check": "payment_check",
                "paid_verification": "paid_verification",  # NEW!
                "negotiation": "negotiation",
                "closing": "closing",
                END: END,
            }
        )

    return graph


app = create_graph().compile()