# src/nodes/negotiation.py

from ..state import CallState
from ..utils.llm import generate_negotiation_response, generate_payment_plans
import re


def extract_amount(text: str) -> float:
    """Extract monetary amount from text."""
    text = text.replace(',', '')
    matches = re.findall(r'[₹Rs.\s]*(\d+(?:\.\d+)?)', text)
    for match in matches:
        amount = float(match)
        if amount > 100:
            return amount
    return None


def extract_date(text: str) -> str:
    """Extract date from text in various formats."""
    text_lower = text.lower()
    
    months_map = {
        'jan': '01', 'january': '01',
        'feb': '02', 'february': '02',
        'mar': '03', 'march': '03',
        'apr': '04', 'april': '04',
        'may': '05',
        'jun': '06', 'june': '06',
        'jul': '07', 'july': '07',
        'aug': '08', 'august': '08',
        'sep': '09', 'september': '09',
        'oct': '10', 'october': '10',
        'nov': '11', 'november': '11',
        'dec': '12', 'december': '12',
    }
    
    for month_name, month_num in months_map.items():
        if month_name in text_lower:
            day_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s*' + month_name, text_lower)
            if not day_match:
                day_match = re.search(month_name + r'\s*(\d{1,2})', text_lower)
            
            if day_match:
                day = day_match.group(1)
                if 1 <= int(day) <= 31:
                    year_match = re.search(r'20\d{2}', text)
                    year = year_match.group(0) if year_match else "2025"
                    return f"{day.zfill(2)}-{month_num}-{year}"
    
    date_pattern = r'(\d{1,2})[-/\s](\d{1,2})[-/\s]?(202[5-9])'
    match = re.search(date_pattern, text)
    if match:
        day, month, year = match.groups()
        if 1 <= int(day) <= 31 and 1 <= int(month) <= 12:
            return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
    
    return None


def has_commitment_details(state: CallState, last_user_input: str) -> tuple:
    """
    Check if customer has provided both amount and date commitment.
    Returns (has_both, amount, date, plan_selected)
    """
    messages = state.get("messages", [])
    offered_plans = state.get("offered_plans", [])
    
    committed_amount = None
    committed_date = None
    selected_plan = None
    
    # Find where verification ended
    verification_done_index = -1
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "").lower()
            if "thank you for confirming" in content or "outstanding payment" in content:
                verification_done_index = i
    
    # Find where plans were offered
    plan_offer_index = -1
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and i > verification_done_index:
            if "option" in msg.get("content", "").lower() or "installment" in msg.get("content", "").lower():
                plan_offer_index = i
                break
    
    start_index = max(plan_offer_index, verification_done_index + 1) if plan_offer_index >= 0 else verification_done_index + 1
    relevant_messages = messages[start_index:] if start_index >= 0 else messages[-3:]
    
    print(f"[COMMITMENT] Checking {len(relevant_messages)} messages after plans offered")
    if offered_plans:
        print(f"[COMMITMENT] Available plans: {[p['name'] for p in offered_plans]}")
    
    for msg in relevant_messages:
        if msg.get("role") == "user":
            content = msg.get("content", "").lower()
            
            print(f"[COMMITMENT] Analyzing user message: '{content}'")
            
            if offered_plans and not selected_plan:
                print(f"[COMMITMENT] Plans available: {len(offered_plans)}")
                month_match = re.search(r'(\d+)\s*month', content)
                if month_match:
                    months = int(month_match.group(1))
                    print(f"[PLAN DETECTION] Found {months}-month mention in: '{content}'")
                    for idx, plan in enumerate(offered_plans):
                        plan_name_lower = plan['name'].lower()
                        plan_desc_lower = plan['description'].lower()
                        
                        print(f"[PLAN DETECTION] Checking plan {idx+1}: '{plan_name_lower}' / '{plan_desc_lower}'")
                        
                        matches = (
                            f"{months}-month" in plan_name_lower or
                            f"{months} month" in plan_desc_lower or
                            f"{months}month" in plan_name_lower.replace("-", "") or
                            (str(months) in plan_name_lower and "month" in plan_name_lower)
                        )
                        
                        if matches:
                            selected_plan = plan
                            print(f"[PLAN DETECTION] ✅ Matched to plan: {plan['name']}")
                            amount_match = re.search(r'₹(\d+(?:,\d+)*)', plan['description'])
                            if amount_match:
                                committed_amount = float(amount_match.group(1).replace(',', ''))
                                print(f"[PLAN DETECTION] Amount: ₹{committed_amount:,.0f}")
                            break
                        else:
                            print(f"[PLAN DETECTION] No match for {months} months")
                
                if not selected_plan:
                    plan_num_match = re.search(r'(?:plan|option)\s*(\d+)', content)
                    if plan_num_match:
                        plan_idx = int(plan_num_match.group(1)) - 1
                        print(f"[PLAN DETECTION] Plan number {plan_idx + 1} selected")
                        if 0 <= plan_idx < len(offered_plans):
                            selected_plan = offered_plans[plan_idx]
                            print(f"[PLAN DETECTION] Matched to: {selected_plan['name']}")
                            amount_match = re.search(r'₹(\d+(?:,\d+)*)', selected_plan['description'])
                            if amount_match:
                                committed_amount = float(amount_match.group(1).replace(',', ''))
                
                if not selected_plan:
                    if 'first' in content or '1st' in content:
                        selected_plan = offered_plans[0]
                    elif 'second' in content or '2nd' in content:
                        selected_plan = offered_plans[min(1, len(offered_plans) - 1)]
                    elif 'third' in content or '3rd' in content:
                        selected_plan = offered_plans[min(2, len(offered_plans) - 1)]
                    
                    if selected_plan:
                        print(f"[PLAN DETECTION] Position-based selection: {selected_plan['name']}")
                        amount_match = re.search(r'₹(\d+(?:,\d+)*)', selected_plan['description'])
                        if amount_match:
                            committed_amount = float(amount_match.group(1).replace(',', ''))
                
                if not selected_plan and any(phrase in content for phrase in ['works for me', 'i\'ll take', 'sounds good', 'that works', 'i accept']):
                    print("[PLAN DETECTION] Acceptance phrase detected")
                    msg_index = messages.index(msg)
                    if msg_index > 0:
                        prev_msg = messages[msg_index - 1]
                        if prev_msg.get("role") == "assistant" and ("option" in prev_msg.get("content", "").lower()):
                            if len(offered_plans) > 1:
                                selected_plan = offered_plans[1]
                            else:
                                selected_plan = offered_plans[0]
                            
                            print(f"[PLAN DETECTION] Assumed plan: {selected_plan['name']}")
                            amount_match = re.search(r'₹(\d+(?:,\d+)*)', selected_plan['description'])
                            if amount_match:
                                committed_amount = float(amount_match.group(1).replace(',', ''))
            
            if not committed_date:
                date = extract_date(content)
                if date:
                    committed_date = date
                    print(f"[DATE DETECTION] Found date: {date}")
            
            if not committed_amount and not selected_plan:
                amount = extract_amount(content)
                if amount:
                    committed_amount = amount
                    print(f"[AMOUNT DETECTION] Found explicit amount: {amount}")
    
    has_both = committed_amount is not None and committed_date is not None
    
    print(f"[COMMITMENT] Final - Amount: {committed_amount}, Date: {committed_date}, Plan: {selected_plan['name'] if selected_plan else None}")
    
    return has_both, committed_amount, committed_date, selected_plan


def negotiation_node(state: CallState) -> dict:
    """
    Have an intelligent conversation with the customer about payment.
    Detects when customer commits to amount AND date, then moves to closing.
    """

    amount = state["outstanding_amount"]
    customer_name = state["customer_name"].split()[0]
    
    last_user_input = state.get("last_user_input") or ""
    messages = state.get("messages", [])
    
    negotiation_turns = 0
    in_negotiation = False
    for msg in messages:
        if msg.get("role") == "assistant":
            content = msg.get("content", "").lower()
            if "outstanding payment" in content or "able to make this payment" in content:
                in_negotiation = False
            elif in_negotiation or any(keyword in content for keyword in ["option", "installment", "plan", "appreciate your willingness"]):
                in_negotiation = True
                negotiation_turns += 1
    
    print(f"[NEGOTIATION] Turn {negotiation_turns + 1}, User input: '{last_user_input}'")
    
    commitment_result = has_commitment_details(state, last_user_input)
    has_both, committed_amount, committed_date, selected_plan = commitment_result
    
    # If we have both - CLOSE IMMEDIATELY
    if has_both:
        print(f"[NEGOTIATION] ✅ Full commitment received - CLOSING NOW")
        
        plan_name = selected_plan['name'] if selected_plan else "Custom Payment Plan"
        
        response = (
            f"Perfect, {customer_name}. I've documented your commitment to the {plan_name} "
            f"with payment of ₹{committed_amount:,.0f} starting on {committed_date}. "
            f"You'll receive a confirmation shortly. Thank you for working this out with us. Have a great day!"
        )
        
        # Return with is_complete=True to END the call
        return {
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": response
            }],
            "ptp_amount": committed_amount,
            "ptp_date": committed_date,
            "selected_plan": selected_plan,
            "stage": "closing",
            "awaiting_user": False,
            "last_user_input": None,
            "payment_status": "willing",
            "call_outcome": "ptp_recorded",
            "is_complete": True,  # THIS ENDS THE CALL
        }
    
    if selected_plan and not committed_date:
        print(f"[NEGOTIATION] Plan selected, asking for date")
        response = (
            f"Great choice, {customer_name}! I've noted the {selected_plan['name']}. "
            f"When would you like to make your first payment?"
        )
        return {
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": response
            }],
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
            "payment_status": "willing",
        }
    
    end_signals = ["no that's all", "no thanks bye", "goodbye", "bye bye", "nothing else", "that's all"]
    user_wants_to_end = any(signal in last_user_input.lower() for signal in end_signals)
    
    should_close = user_wants_to_end or negotiation_turns >= 8
    
    if should_close:
        print(f"[NEGOTIATION] Closing conversation (user_wants_to_end={user_wants_to_end}, turns={negotiation_turns})")
        response = (
            f"Thank you, {customer_name}. I've documented our discussion. "
            f"We'll follow up with you shortly to finalize the arrangement. "
            f"Have a good day."
        )
        return {
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": response
            }],
            "stage": "negotiation",
            "awaiting_user": False,
            "last_user_input": None,
        }
    
    plan_request_keywords = [
        "payment plan", "installment", "emi", "monthly payment",
        "break it up", "pay in parts", "split", "work out a plan",
        "options", "what are my options", "can you offer"
    ]
    
    is_plan_request = any(keyword in last_user_input.lower() for keyword in plan_request_keywords)
    
    if negotiation_turns == 0 or (is_plan_request and not state.get("offered_plans")):
        try:
            plans = generate_payment_plans(amount, customer_name)
        except Exception as e:
            print(f"[NEGOTIATION] Error generating plans: {e}, using fallback")
            from ..utils.llm import generate_fallback_plans
            plans = generate_fallback_plans(amount)
        
        if plans and len(plans) > 0:
            if negotiation_turns == 0:
                response = f"I appreciate your willingness to work this out, {customer_name}. Let me show you some options:\n\n"
            else:
                response = f"Of course, {customer_name}. Here are some payment options:\n\n"
            
            for i, plan in enumerate(plans, 1):
                response += f"{i}. **{plan['name']}**: {plan['description']}\n"
            
            response += f"\nWhich option works best for you?"
            
            return {
                "offered_plans": plans,
                "messages": state["messages"] + [{
                    "role": "assistant",
                    "content": response
                }],
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
                "payment_status": "willing",
            }
        else:
            return {
                "messages": state["messages"] + [{
                    "role": "assistant",
                    "content": (
                        f"I appreciate your willingness to work this out, {customer_name}. "
                        f"Could you let me know what monthly amount and date would work for you?"
                    )
                }],
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
                "payment_status": "willing",
            }
    
    recent_conversation = ""
    for msg in messages[-6:]:
        role = "Agent" if msg["role"] == "assistant" else "Customer"
        recent_conversation += f"{role}: {msg['content']}\n"
    
    plans_context = ""
    if state.get("offered_plans"):
        plans_context = "\n\nOffered plans:\n"
        for plan in state["offered_plans"]:
            plans_context += f"- {plan['name']}: {plan['description']}\n"
    
    context = f"""You are a professional debt collection agent.

Customer: {customer_name}
Outstanding: ₹{amount:,.0f}

Recent conversation:
{recent_conversation}
{plans_context}

Customer said: "{last_user_input}"

Task: Respond naturally. If they selected a plan, confirm it and ask for payment date. If they mentioned a date, confirm it. Be brief (2-3 sentences).

Response:"""

    response = generate_negotiation_response(context)
    
    if not response:
        print("[NEGOTIATION] Using smart template fallback")
        
        if committed_date and not committed_amount and not selected_plan:
            response = (
                f"Thank you for that date, {customer_name}. "
                f"Could you confirm which payment plan works best for you?"
            )
        else:
            response = (
                f"I appreciate your input, {customer_name}. "
                f"To finalize this, could you confirm the payment plan and date that work for you?"
            )
    
    return {
        "messages": state["messages"] + [{
            "role": "assistant",
            "content": response
        }],
        "stage": "negotiation",
        "awaiting_user": True,
        "last_user_input": None,
        "payment_status": "willing",
    }