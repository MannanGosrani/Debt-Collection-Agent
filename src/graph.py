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
    
    stage = state.get("stage")
    is_complete = state.get("is_complete")
    awaiting_user = state.get("awaiting_user")
    
    # If call is complete, end
    if is_complete:
        return END
    
    # If awaiting user input, pause
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
        
        # If immediate payment was recorded (has reason), go to negotiation to finalize
        if state.get("awaiting_reason_for_delay") and state.get("pending_ptp_amount"):
            print("[ROUTING] Collecting reason for immediate payment")
            return "negotiation"
        
        # If customer claims paid, verify first
        if payment_status == "paid":
            print("[ROUTING] Paid claim, going to paid_verification")
            return "paid_verification"
        
        # If callback - check callback_mode
        if payment_status == "callback":
            callback_mode = state.get("callback_mode")
            
            if callback_mode == "partial_payment_attempt":
                # Stay in payment_check to see if they commit to partial
                print("[ROUTING] Callback - waiting for partial payment response")
                return END
            else:
                # Direct callback request without negotiation attempt
                print("[ROUTING] Callback without payment, going to closing")
                return "closing"
        
        # If customer wants to negotiate, go to negotiation
        if payment_status == "willing":
            print("[ROUTING] Willing, going to negotiation")
            return "negotiation"
        
        # All other statuses (disputed, unable) go to closing
        print(f"[ROUTING] {payment_status}, going to closing")
        return "closing"
    
    elif stage == "paid_verification":
        payment_status = state.get("payment_status")
        
        if payment_status == "paid":
            print("[ROUTING] Verification done, going to closing")
            return "closing"
        elif payment_status == "willing":
            print("[ROUTING] No proof, going to negotiation")
            return "negotiation"
        
        return "closing"
    
    elif stage == "negotiation":
        # Check if escalated - go to closing
        if state.get("has_escalated"):
            print("[ROUTING] Escalated, going to closing")
            return "closing"
        
        # Check if PTP saved and WhatsApp confirmation complete
        if state.get("ptp_id") and state.get("is_complete"):
            print("[ROUTING] PTP confirmed via WhatsApp, ending")
            return END
        
        # Check if awaiting reason before recording PTP
        if state.get("awaiting_reason_for_delay"):
            print("[ROUTING] Waiting for delay reason")
            return END
        
        # Check if awaiting WhatsApp confirmation
        if state.get("awaiting_whatsapp_confirmation"):
            print("[ROUTING] Waiting for WhatsApp confirmation")
            return END
        
        # Check if PTP saved - go to closing
        if state.get("ptp_id"):
            print("[ROUTING] PTP saved in negotiation, going to closing")
            return "closing"
        
        # Stay in negotiation
        return "negotiation"
    
    elif stage == "closing":
        # Check if collecting callback reason
        if state.get("awaiting_callback_reason"):
            print("[ROUTING] Waiting for callback reason")
            return END
        
        # Check if collecting escalation reason
        if state.get("awaiting_escalation_reason"):
            print("[ROUTING] Waiting for escalation reason")
            return END
        
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