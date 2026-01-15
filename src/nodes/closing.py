# src/nodes/closing.py

from ..state import CallState
from ..data import save_call_record, save_dispute, save_ptp


def closing_node(state: CallState) -> dict:
    """
    End the conversation with appropriate pressure and consequences.
    Collects reason for delay before closing callback/escalation scenarios.
    """
    
    # PRIORITY: Handle escalation first
    if state.get("has_escalated"):
        customer_name = state["customer_name"].split()[0]
        outstanding = state.get("outstanding_amount", 0)
        
        # Check if we need to collect reason for delay
        if not state.get("escalation_reason_collected"):
            print("[CLOSING] Collecting reason before escalation")
            
            response = (
                f"{customer_name}, before I escalate this case, "
                f"could you tell me why you're unable to make any payment arrangement today?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "awaiting_escalation_reason": True,
                "stage": "closing",
                "awaiting_user": True,
                "last_user_input": None,
            }
        
        # Reason collected, now escalate
        escalation_reason = state.get("escalation_reason", "Customer refused all payment options")
        
        escalation_message = (
            f"{customer_name}, no resolution has been reached.\n\n"
            f"This account will now be escalated.\n"
            f"Further delays may result in serious credit and recovery action."
        )
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": escalation_message}],
            "call_outcome": "escalated",
            "escalation_reason": escalation_reason,
            "stage": "closing",
            "awaiting_user": False,
            "is_complete": True,
        }
    
    # Check if collecting escalation reason
    if state.get("awaiting_escalation_reason"):
        reason = state.get("last_user_input", "No reason provided")
        
        return {
            "escalation_reason": reason,
            "escalation_reason_collected": True,
            "stage": "closing",
            "awaiting_user": False,
        }
    
    # Check for conversation end requests during closing
    last_input = state.get("last_user_input", "")
    customer_name = state["customer_name"].split()[0]
    
    if last_input:
        user_lower = last_input.lower().strip()
        end_keywords = [
            "end convo", "end conversation", "end chat",
            "stop", "exit", "quit", "goodbye", "bye",
            "leave me alone", "stop calling"
        ]
        
        if any(keyword in user_lower for keyword in end_keywords):
            print("[CLOSING] User requested to end during closing - completing immediately")
            
            response = (
                f"{customer_name}, this conversation is now ending.\n\n"
                f"Your account status remains unchanged. "
                f"Legal action may be initiated if payment is not received within 7 days."
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "call_outcome": "customer_ended_call",
                "has_escalated": True,
                "stage": "closing",
                "awaiting_user": False,
                "is_complete": True,
            }
    
    # Check if collecting callback reason (UPDATED - Lines 100-120)
    if state.get("awaiting_callback_reason"):
        reason = state.get("last_user_input", "Customer needs time")
        
        outstanding = state.get("outstanding_amount", 0)
        days_overdue = state.get("days_past_due", 0)
        
        # Provide stern closing message
        closing_message = (
            f"Thank you for sharing, {customer_name}.\n\n"
            f"However, I must emphasize:\n"
            f"• Your account is {days_overdue} days overdue\n"
            f"• Late charges of ₹{outstanding * 0.02:,.0f}/day continue to accumulate\n"
            f"• Your credit score is being negatively impacted\n"
            f"• If payment is not received within 7 days, legal action may be initiated\n\n"
            f"This case will be escalated. We strongly recommend making payment immediately."
        )
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": closing_message}],
            "callback_reason": reason,
            "callback_reason_collected": True,
            "call_outcome": "escalated",
            "stage": "closing",
            "awaiting_user": False,
            "is_complete": True,
        }
    
    payment_status = state.get("payment_status", "completed")
    outstanding = state.get("outstanding_amount", 0)
    days_overdue = state.get("days_past_due", 0)
    
    # Generate closing message based on outcome
    if payment_status == "paid":
        closing_message = (
            f"Thank you, {customer_name}. I'll verify the payment on our end and update your account. "
            f"If there are any discrepancies, we'll reach out within 24 hours."
        )
        outcome = "paid"
        
    elif payment_status == "disputed":
        dispute_reason = state.get("last_user_input")
        if not dispute_reason:
            messages = state.get("messages", [])
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    dispute_reason = msg.get("content", "Customer disputes the debt")
                    break
        if not dispute_reason:
            dispute_reason = "Customer disputes the debt"
        
        dispute_id = save_dispute(state["customer_id"], dispute_reason)
        
        closing_message = (
            f"I understand you're disputing this debt, {customer_name}. "
            f"I've created a dispute ticket (Reference: DSP{dispute_id}) and our disputes team will review this carefully. "
            f"Our team will contact you within 3-5 business days. "
            f"However, please note that late payment charges will continue to accrue until this is resolved, "
            f"and your credit score may be impacted. "
            f"Thank you for bringing this to our attention."
        )
        outcome = "disputed"
        state["dispute_id"] = dispute_id
        state["dispute_reason"] = dispute_reason
        
    elif payment_status == "callback":
        # UPDATED - Lines 180-200: Check if reason collected
        if not state.get("callback_reason_collected"):
            print("[CLOSING] Collecting callback reason")
            
            response = (
                f"{customer_name}, before this case is escalated, "
                f"could you tell me why you're unable to make any payment arrangement today?\n\n"
                f"Please note: Late charges of ₹{outstanding * 0.02:,.0f}/day continue to accumulate."
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "awaiting_callback_reason": True,
                "stage": "closing",
                "awaiting_user": True,
                "last_user_input": None,
            }
        
        # This block shouldn't be reached since awaiting_callback_reason handles it above
        # But keeping it as fallback
        callback_reason = state.get("callback_reason", "Customer requested callback")
        
        closing_message = (
            f"{customer_name}, I understand you need time. However, I must inform you:\n\n"
            f"• Your account is {days_overdue} days overdue\n"
            f"• Late charges of ₹{outstanding * 0.02:,.0f}/day are being added\n"
            f"• Your credit score is being negatively impacted right now\n"
            f"• If payment is not received within 7 days, legal action may be initiated\n\n"
            f"We'll follow up with a reminder shortly. I strongly recommend making a payment as soon as possible to avoid escalation."
        )
        outcome = "callback"
    
    elif payment_status == "unable":
        closing_message = (
            f"I understand you're facing financial difficulties, {customer_name}. "
            f"However, you must understand the consequences of non-payment:\n\n"
            f"• Daily late charges continue to accumulate\n"
            f"• Your credit score will drop significantly\n"
            f"• This will affect your ability to get loans, credit cards, or even rent an apartment in the future\n"
            f"• Legal proceedings may be initiated, which could result in asset seizure\n\n"
            f"I'll escalate this to our hardship team to see if we can work out a solution. "
            f"They will contact you within 48 hours. "
            f"In the meantime, I urge you to make any payment you can afford to show good faith."
        )
        outcome = "unable"
        
    elif payment_status == "willing":
        # Check if PTP was already recorded
        if state.get("ptp_id"):
            ptp_id = state.get("ptp_id")
            ptp_amount = state.get("ptp_amount")
            ptp_date = state.get("ptp_date")
            
            # Generate payment link
            payment_link = f"https://abc-finance.com/pay/PTP{ptp_id}"
            
            if state.get("selected_plan"):
                plan_name = state.get("selected_plan", {}).get("name", "payment plan")
                closing_message = (
                    f"Excellent, {customer_name}. I've recorded your commitment:\n\n"
                    f"• Plan: {plan_name}\n"
                    f"• Amount: ₹{ptp_amount:,.0f}\n"
                    f"• Date: {ptp_date}\n"
                    f"• Reference: PTP{ptp_id}\n\n"
                    f"**Payment Link:** {payment_link}\n\n"
                    f"Use this link to make your payment. "
                    f"Please note: If payment is not received by the committed date, "
                    f"late charges will continue to accrue and your case will be escalated to our legal team."
                )
            else:
                closing_message = (
                    f"Good decision, {customer_name}. I've documented your commitment to pay ₹{ptp_amount:,.0f} on {ptp_date}.\n\n"
                    f"Reference Number: PTP{ptp_id}\n\n"
                    f"**Payment Link:** {payment_link}\n\n"
                    f"Please complete the payment by {ptp_date} as committed. "
                    f"Failure to pay will result in additional late charges and potential legal action."
                )
            
            outcome = "ptp_recorded"
        else:
            # No specific commitment yet
            closing_message = (
                f"{customer_name}, while I appreciate you discussing payment options with me, "
                f"I need you to understand the urgency of this situation:\n\n"
                f"• Your account is {days_overdue} days overdue\n"
                f"• Outstanding amount: ₹{outstanding:,.0f}\n"
                f"• Daily late charges are being added\n"
                f"• Your credit score is dropping\n\n"
                f"I strongly urge you to make a payment commitment today. "
                f"Our team will follow up with you within 24 hours. "
                f"If we don't hear from you or receive payment, your case will be escalated to our collections department."
            )
            outcome = "willing"
        
    else:
        closing_message = (
            f"{customer_name}, this call is to remind you that your account is {days_overdue} days overdue "
            f"with an outstanding balance of ₹{outstanding:,.0f}.\n\n"
            f"Immediate action is required to avoid:\n"
            f"• Additional late payment charges\n"
            f"• Severe credit score damage\n"
            f"• Potential legal action\n\n"
            f"Please make payment as soon as possible."
        )
        outcome = payment_status or "completed"

    # Check if closing message asks a question
    asks_question = closing_message.strip().endswith('?')
    
    if asks_question and not state.get("closing_question_asked"):
        print("[CLOSING] Message asks question, waiting for response")
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": closing_message}],
            "closing_question_asked": True,
            "call_outcome": outcome,
            "stage": "closing",
            "awaiting_user": True,
            "last_user_input": None,
        }
    
    # No question OR already got response - actually close
    print("[CLOSING] Completing call")
    
    # Create call summary
    summary = f"""
Chat completed.
Verified: {state['is_verified']}
Outcome: {outcome}
Payment Status: {payment_status}
Customer: {state['customer_name']}
Outstanding Amount: ₹{state['outstanding_amount']}
Days Overdue: {days_overdue}
"""
    
    if state.get("delay_reason"):
        summary += f"Delay Reason: {state['delay_reason']}\n"
    if state.get("callback_reason"):
        summary += f"Callback Reason: {state['callback_reason']}\n"
    if state.get("escalation_reason"):
        summary += f"Escalation Reason: {state['escalation_reason']}\n"

    # Save call record
    save_call_record({
        "customer_id": state["customer_id"],
        "outcome": outcome,
        "payment_status": payment_status,
        "summary": summary.strip()
    })

    return {
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": closing_message
        }],
        "call_outcome": outcome,
        "call_summary": summary.strip(),
        "is_complete": True,
        "stage": "closing",
        "awaiting_user": False,
    }