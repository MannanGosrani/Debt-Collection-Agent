# src/nodes/negotiation.py 

from ..state import CallState
from ..utils.llm import generate_negotiation_response, generate_payment_plans
from ..data import save_ptp
from datetime import datetime, timedelta
import re


def extract_amount(text: str) -> float:
    """
    Extract monetary amount from text.
    CRITICAL FIXES:
    - Don't extract years like "2026" from dates
    - Handle ranges like "10-15k"
    - Handle percentages like "50%"
    """
    text_lower = text.lower()
    
    # CRITICAL FIX: Skip if this looks like a date with year
    if re.search(r'\b(202[5-9]|203[0-9])\b', text):
        date_patterns = [
            r'\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(202[5-9]|203[0-9])',
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:st|nd|rd|th)?\s+(202[5-9]|203[0-9])',
        ]
        for pattern in date_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                print(f"[AMOUNT] Skipping year in date: {text}")
                text = re.sub(r'\b(202[5-9]|203[0-9])\b', '', text)
    
    # Remove commas and currency symbols
    text = text.replace(',', '').replace('₹', '').replace('Rs', '').replace('rs', '')
    
    # CRITICAL FIX: Handle ranges like "10-15k"
    range_pattern = r'(\d+)\s*-\s*(\d+)\s*k'
    range_match = re.search(range_pattern, text_lower)
    if range_match:
        print(f"[AMOUNT] Found range, need clarification: {text}")
        return None  # Let agent ask for clarification
    
    # Try amounts with 'k' notation
    k_pattern = r'(\d+(?:\.\d+)?)\s*k'
    k_match = re.search(k_pattern, text_lower)
    if k_match:
        amount = float(k_match.group(1)) * 1000
        if 100 < amount < 1000000:
            print(f"[AMOUNT] Extracted from 'k' notation: ₹{amount:,.0f}")
            return amount
    
    # Try standalone numbers (but avoid dates)
    # Only if there's clear payment context
    payment_context = ['pay', 'give', 'amount', 'rupees', 'rs', '₹']
    if any(word in text_lower for word in payment_context):
        # Look for standalone numbers
        standalone_pattern = r'\b(\d{4,})\b'
        matches = re.findall(standalone_pattern, text)
        for match in matches:
            # Skip if it's a year
            if not re.match(r'202[5-9]|203[0-9]', match):
                amount = float(match)
                if 100 < amount < 1000000:
                    print(f"[AMOUNT] Extracted standalone amount: ₹{amount:,.0f}")
                    return amount
    
    return None


def extract_percentage(text: str, total_amount: float) -> float:
    """
    Extract percentage and calculate amount.
    E.g., "50%" of 52500 = 26250
    
    CRITICAL FIX: Don't extract if discussing discount/rate, only if offering payment
    """
    text_lower = text.lower()
    
    # Don't extract if discussing discount percentages
    discount_indicators = [
        "discount", "rate", "interest", "percent off",
        "% off", "% discount", "enough", "not enough",
        "can you do", "give me", "offer", "better"
    ]
    if any(indicator in text_lower for indicator in discount_indicators):
        print(f"[AMOUNT] Skipping percentage - discussing discount: '{text}'")
        return None
    
    # Only extract if clearly offering to pay a percentage
    payment_indicators = [
        "i can pay", "i'll pay", "pay", "give you", "send",
        "i have", "afford"
    ]
    has_payment_context = any(indicator in text_lower for indicator in payment_indicators)
    
    percent_pattern = r'(\d+(?:\.\d+)?)\s*%'
    match = re.search(percent_pattern, text)
    if match and has_payment_context:
        percentage = float(match.group(1))
        if 0 < percentage <= 100:
            amount = (percentage / 100) * total_amount
            print(f"[AMOUNT] Calculated {percentage}% of ₹{total_amount:,.0f} = ₹{amount:,.0f}")
            return amount
    
    return None


def has_multiple_payment_dates(text: str) -> bool:
    """
    Detect if user mentions multiple payment dates/installments.
    E.g., "10000 on Jan 5 and rest on Feb 5"
    """
    text_lower = text.lower()
    
    # Multiple date indicators
    multi_indicators = [
        "and the rest on", "and rest on", "remaining on",
        "then", "followed by", "and then",
        "first payment", "second payment", "installment"
    ]
    
    # Check if mentions multiple dates
    months_map = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    month_count = sum(1 for month in months_map if month in text_lower)
    
    has_indicator = any(indicator in text_lower for indicator in multi_indicators)
    
    if month_count >= 2 or (has_indicator and month_count >= 1):
        print(f"[DATE DETECTION] Multiple payment dates detected")
        return True
    
    return False


def extract_date(text: str) -> str:
    """
    Extract date from text in various formats.
    CRITICAL FIXES:
    - Skip "3 month plan" → don't extract "3" as date
    - Skip "10-15k" → don't extract "10" as date
    - Handle date ranges by asking for clarification
    """
    text_lower = text.lower()
    
    # CRITICAL: Skip if this looks like a plan selection
    plan_keywords = ["month plan", "installment", "option", "settlement"]
    if any(keyword in text_lower for keyword in plan_keywords):
        # Only extract if there's an EXPLICIT date with timing words
        explicit_date_patterns = [
            r'starting\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
            r'starting\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}',
            r'from\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
            r'from\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}',
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
            r'\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}',
        ]
        has_explicit_date = any(re.search(pattern, text_lower) for pattern in explicit_date_patterns)
        if not has_explicit_date:
            print(f"[DATE DETECTION] Skipping plan selection text: '{text_lower}'")
            return None
        else:
            print(f"[DATE DETECTION] Found explicit date in plan selection: '{text_lower}'")
    
    # CRITICAL: Skip if this looks like an amount range
    if re.search(r'\d+\s*-\s*\d+\s*k', text_lower):
        print(f"[DATE DETECTION] Skipping amount range: '{text_lower}'")
        return None
    
    # CRITICAL: Handle date ranges (ask for clarification later)
    date_range_pattern = r'between\s+(\d{1,2})(?:st|nd|rd|th)?\s+and\s+(\d{1,2})(?:st|nd|rd|th)?'
    range_match = re.search(date_range_pattern, text_lower)
    if range_match:
        # Take first date in range
        day = range_match.group(1)
        month = datetime.now().strftime("%m")
        year = datetime.now().strftime("%Y")
        print(f"[DATE DETECTION] Found date range, using first date: {day}")
        return f"{day.zfill(2)}-{month}-{year}"
    
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
    
    # Try to find month name first
    for month_name, month_num in months_map.items():
        if month_name in text_lower:
            # Pattern: "22nd july" or "july 22"
            day_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s*' + month_name, text_lower)
            if not day_match:
                day_match = re.search(month_name + r'\s*(\d{1,2})(?:st|nd|rd|th)?', text_lower)
            
            if day_match:
                day = day_match.group(1)
                if 1 <= int(day) <= 31:
                    year_match = re.search(r'20\d{2}', text)
                    year = year_match.group(0) if year_match else "2026"
                    return f"{day.zfill(2)}-{month_num}-{year}"
    
    # Try DD-MM-YYYY or DD/MM/YYYY format
    date_pattern = r'(\d{1,2})[-/\s](\d{1,2})(?:[-/\s]?(202[5-9]))?'
    match = re.search(date_pattern, text)
    if match:
        day, month, year = match.groups()
        if 1 <= int(day) <= 31 and 1 <= int(month) <= 12:
            year = year if year else "2026"
            return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
    
    # Relative dates
    today = datetime.now()
    
    if "tomorrow" in text_lower:
        tomorrow = today + timedelta(days=1)
        return tomorrow.strftime("%d-%m-%Y")
    elif "day after tomorrow" in text_lower:
        day_after = today + timedelta(days=2)
        return day_after.strftime("%d-%m-%Y")
    
    # Don't process vague "next week" or "next month" - let agent ask for specific date
    
    return None


def is_negative_response(text: str) -> bool:
    """
    Detect if user is giving a negative/rejection response.
    CRITICAL FIX: Don't treat interest phrases as negative!
    """
    text_lower = text.lower().strip()
    
    # CRITICAL: Exclude phrases showing interest or conditional willingness
    interest_phrases = [
        "maybe", "perhaps", "might", "could", "can pay", "i can",
        "later today", "if i", "when i", "i want", "willing to",
        "50%", "percent", "partial", "some"
    ]
    if any(phrase in text_lower for phrase in interest_phrases):
        print(f"[COMMITMENT] Found interest phrase in: '{text_lower}'")
        return False
    
    # Strong negatives only
    negative_signals = [
        "none of these", "none of those", "none work",
        "doesn't work", "dont work", "don't work",
        "no plan", "no option",
        "not interested", "don't want", "dont want"
    ]
    
    for signal in negative_signals:
        if signal in text_lower:
            return True
    
    return False


def is_requesting_lower_amount(text: str) -> bool:
    """Detect if customer is asking to lower the payment amount."""
    lower_phrases = [
        "too high", "too much", "too expensive",
        "can you lower", "lower it", "reduce", "decrease",
        "less", "cheaper", "can't afford that", "cant afford that"
    ]
    return any(phrase in text.lower() for phrase in lower_phrases)


def detect_plan_change(text: str, current_plan: dict, available_plans: list) -> dict:
    """
    Detect if customer is changing their mind about the plan.
    Returns new plan if detected, otherwise None.
    """
    text_lower = text.lower()
    
    # Change indicators
    change_phrases = ["wait", "actually", "instead", "rather", "change", "switch"]
    if not any(phrase in text_lower for phrase in change_phrases):
        return None
    
    # Try to find new plan mentioned
    for plan in available_plans:
        if plan != current_plan:
            # Check for month count
            month_match = re.search(r'(\d+)\s*[-]?\s*month', plan['name'].lower())
            if month_match:
                months = month_match.group(1)
                if months in text_lower and "month" in text_lower:
                    print(f"[PLAN CHANGE] Detected change from {current_plan['name']} to {plan['name']}")
                    return plan
    
    return None


def detect_plan_by_feature(text: str, offered_plans: list) -> dict:
    """
    Detect plan selection by feature/characteristic.
    E.g., "the one with the discount"
    """
    text_lower = text.lower()
    
    # Feature keywords
    feature_map = {
        'discount': lambda p: 'discount' in p['description'].lower() or 'discount' in p['name'].lower(),
        'immediate': lambda p: 'immediate' in p['name'].lower(),
        'settlement': lambda p: 'settlement' in p['name'].lower(),
        'installment': lambda p: 'installment' in p['name'].lower(),
        'lowest': lambda p: True,  # Will pick last plan (usually lowest monthly)
        'cheapest': lambda p: True,
    }
    
    for feature, matcher in feature_map.items():
        if feature in text_lower:
            matching_plans = [p for p in offered_plans if matcher(p)]
            if matching_plans:
                if feature in ['lowest', 'cheapest']:
                    # Return last plan (usually 6-month with lowest monthly)
                    return matching_plans[-1]
                else:
                    return matching_plans[0]
    
    return None


def has_commitment_details(state: CallState, last_user_input: str) -> tuple:
    """
    Check if customer has provided plan, amount, and/or date commitment.
    Returns (has_complete_commitment, amount, date, plan)
    
    CRITICAL FIXES:
    - Don't treat "maybe later" as negative
    - Handle "anything except first" correctly
    - Detect plan changes
    - Extract percentages
    """
    messages = state.get("messages", [])
    offered_plans = state.get("offered_plans", [])
    outstanding_amount = state.get("outstanding_amount")
    
    committed_amount = None
    committed_date = None
    selected_plan = None
    
    # CRITICAL FIX: Find where DISCLOSURE happened (not just plans)
    # This prevents extracting DOB as payment date!
    disclosure_index = -1
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "").lower()
            if "outstanding" in content and "amount" in content:
                disclosure_index = i
                break
    
    # Find where plans were offered (after disclosure)
    plan_offer_index = -1
    for i, msg in enumerate(messages):
        if i > disclosure_index and msg.get("role") == "assistant":
            content = msg.get("content", "").lower()
            if ("option" in content or "installment" in content) and "outstanding" not in content:
                plan_offer_index = i
                break
    
    # CRITICAL: Only analyze messages AFTER disclosure, not from the beginning!
    # This prevents DOB from verification being extracted as payment date
    if plan_offer_index >= 0:
        start_index = plan_offer_index + 1
    elif disclosure_index >= 0:
        # Plans not shown yet, but start after disclosure
        start_index = disclosure_index + 1
    else:
        # Fallback: last 3 messages only
        start_index = max(0, len(messages) - 3)
    
    relevant_messages = messages[start_index:] if start_index < len(messages) else []
    
    print(f"[COMMITMENT] Checking {len(relevant_messages)} messages (start_index={start_index}, disclosure={disclosure_index}, plans={plan_offer_index})")
    if offered_plans:
        print(f"[COMMITMENT] Available plans: {[p['name'] for p in offered_plans]}")
    
    for msg in relevant_messages:
        if msg.get("role") == "user":
            content = msg.get("content", "").lower()
            print(f"[COMMITMENT] Analyzing user message: '{content}'")
            
            # Skip negative responses
            if is_negative_response(content):
                print(f"[COMMITMENT] Negative response detected: '{content}'")
                continue
            
            # Try to detect plan if we have offered_plans
            if offered_plans and not selected_plan:
                print(f"[COMMITMENT] Plans available: {len(offered_plans)}")
                
                # Check for negative selection ("anything except first")
                if re.search(r'(?:anything|any)\s+(?:except|but|not)\s+(?:the\s+)?(?:first|1st|one)', content):
                    print(f"[PLAN DETECTION] Negative selection detected - needs clarification")
                    continue
                
                # Try feature-based selection first
                feature_plan = detect_plan_by_feature(content, offered_plans)
                if feature_plan:
                    selected_plan = feature_plan
                    print(f"[PLAN DETECTION] Feature-based match: {selected_plan['name']}")
                    amount_match = re.search(r'₹(\d+(?:,\d+)*)', selected_plan['description'])
                    if amount_match:
                        committed_amount = float(amount_match.group(1).replace(',', ''))
                
                # Try month count matching
                if not selected_plan:
                    month_match = re.search(r'(\d+)\s*[-]?\s*month', content)
                    if month_match:
                        months = int(month_match.group(1))
                        print(f"[PLAN DETECTION] Found {months}-month mention")
                        for plan in offered_plans:
                            plan_lower = plan['name'].lower() + ' ' + plan['description'].lower()
                            if f"{months}-month" in plan_lower or f"{months} month" in plan_lower:
                                selected_plan = plan
                                print(f"[PLAN DETECTION] ✅ Matched to: {plan['name']}")
                                amount_match = re.search(r'₹(\d+(?:,\d+)*)', plan['description'])
                                if amount_match:
                                    committed_amount = float(amount_match.group(1).replace(',', ''))
                                break
                
                # Try position-based selection
                if not selected_plan:
                    position_keywords = [
                        ('first', 0), ('1st', 0),
                        ('second', 1), ('2nd', 1),
                        ('third', 2), ('3rd', 2),
                    ]
                    
                    for keyword, idx in sorted(position_keywords, key=lambda x: len(x[0]), reverse=True):
                        # Only match if NOT preceded by "except" or "not"
                        if keyword in content and "except" not in content and "not the" not in content:
                            if idx < len(offered_plans):
                                selected_plan = offered_plans[idx]
                                print(f"[PLAN DETECTION] Position-based ({keyword}): {selected_plan['name']}")
                                amount_match = re.search(r'₹(\d+(?:,\d+)*)', selected_plan['description'])
                                if amount_match:
                                    committed_amount = float(amount_match.group(1).replace(',', ''))
                            break
                
            
            # Check for plan change if plan already selected
            if selected_plan:
                new_plan = detect_plan_change(content, selected_plan, offered_plans)
                if new_plan:
                    selected_plan = new_plan
                    amount_match = re.search(r'₹(\d+(?:,\d+)*)', new_plan['description'])
                    if amount_match:
                        committed_amount = float(amount_match.group(1).replace(',', ''))
                        print(f"[PLAN CHANGE] Updated amount: ₹{committed_amount:,.0f}")
            
            # Extract date
            if not committed_date:
                # CRITICAL FIX: Check for multiple payment dates first
                if has_multiple_payment_dates(content):
                    print(f"[DATE DETECTION] Multiple payment dates - user needs guidance")
                    # Mark this for special handling but extract first date
                    date = extract_date(content)
                    if date:
                        # We'll handle this in negotiation_node with a special flag
                        committed_date = date
                        # Set a flag to indicate multiple dates were mentioned
                        # (This will be checked in negotiation_node)
                else:
                    date = extract_date(content)
                    if date:
                        committed_date = date
                        print(f"[DATE DETECTION] Found date: {date}")
            
            # Extract amount or percentage (if no plan selected)
            if not committed_amount and not selected_plan:
                # Try percentage first
                percentage_amount = extract_percentage(content, outstanding_amount)
                if percentage_amount:
                    committed_amount = percentage_amount
                else:
                    # Try regular amount
                    amount = extract_amount(content)
                    if amount:
                        committed_amount = amount
                        print(f"[AMOUNT DETECTION] Found explicit amount: {amount}")
    
    # Final validation
    has_complete = (
        (committed_amount is not None and committed_date is not None) or
        (selected_plan is not None and committed_date is not None)
    )
    
    print(f"[COMMITMENT] Final - Amount: {committed_amount}, Date: {committed_date}, Plan: {selected_plan['name'] if selected_plan else None}")
    
    return has_complete, committed_amount, committed_date, selected_plan


def negotiation_node(state: CallState) -> dict:
    """
    AI-POWERED negotiation with intelligent, contextual responses.
    """
    # HARD STOP: If escalated, do nothing further
    if state.get("stage") == "escalation":
        print("[NEGOTIATION] Already escalated - stopping further messages")
        return {
            "awaiting_user": False,
            "is_complete": True,
        }
        
    # CRITICAL CHECK: If PTP already recorded (immediate payment), don't negotiate
    if state.get("ptp_id") and state.get("is_complete"):
        print("[NEGOTIATION] PTP already recorded and complete - skipping negotiation")
        return {
            "stage": "negotiation",
            "awaiting_user": False,
            "is_complete": True,
        }
    
    amount = state["outstanding_amount"]
    customer_name = state["customer_name"].split()[0]
    last_user_input = state.get("last_user_input") or ""
    messages = state.get("messages", [])
    offered_plans = state.get("offered_plans", [])
    
    # Count negotiation turns
    negotiation_turns = sum(1 for msg in messages if msg.get("role") == "assistant" and any(
        keyword in msg.get("content", "").lower() for keyword in ["option", "installment", "plan"]
    ))
    
    print(f"[NEGOTIATION] Turn {negotiation_turns + 1}, User input: '{last_user_input}'")
    
    # ================================================================
    # PRIORITY 1: Negative selection ("anything except first")
    # ================================================================
    if re.search(r'(?:anything|any)\s+(?:except|but|not)\s+(?:the\s+)?(?:first|1st|one|second|2nd|third|3rd)', last_user_input.lower()):
        print(f"[NEGOTIATION] Negative selection detected")
        
        ai_result = generate_negotiation_response(
            situation="negative_plan_selection",
            customer_name=customer_name,
            outstanding_amount=amount,
            conversation_history=messages,
            last_user_input=last_user_input,
            offered_plans=offered_plans,
            context_note="Customer said 'anything except X', needs clarification on which plan they want"
        )
        
        if ai_result and ai_result.get('response'):
            response = ai_result['response']
        else:
            response = f"I understand that doesn't work, {customer_name}. Which of the other options would work better? We need to resolve this today to prevent further credit damage."
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
            "payment_status": "willing",
        }
    
    # ================================================================
    # PRIORITY 2: Multiple payment dates mentioned
    # ================================================================
    if has_multiple_payment_dates(last_user_input):
        print(f"[NEGOTIATION] Multiple payment dates detected")
        
        # Generate plans if not shown yet
        if negotiation_turns == 0:
            plans = generate_payment_plans(amount, customer_name)
            
            ai_result = generate_negotiation_response(
                situation="multiple_dates_mentioned_first_turn",
                customer_name=customer_name,
                outstanding_amount=amount,
                conversation_history=messages,
                last_user_input=last_user_input,
                offered_plans=plans,
                context_note="Customer mentioned multiple dates (e.g., '10k on Jan 5 and rest on Feb 5'). Show structured installment plans."
            )
            
            if ai_result and ai_result.get('response'):
                response = ai_result['response']
            else:
                response = (
                    f"{customer_name}, here are your payment options:\n\n"
                    + "\n".join([f"{i+1}. **{p['name']}**: {p['description']}" for i, p in enumerate(plans)])
                    + "\n\nWhich plan works for you?"
                )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "offered_plans": plans,
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
                "payment_status": "willing",
            }
        else:
            ai_result = generate_negotiation_response(
                situation="multiple_dates_after_plans_shown",
                customer_name=customer_name,
                outstanding_amount=amount,
                conversation_history=messages,
                last_user_input=last_user_input,
                offered_plans=offered_plans,
                context_note="Plans already shown. Customer still mentioning multiple dates. Guide to pick one plan."
            )
            
            if ai_result and ai_result.get('response'):
                response = ai_result['response']
            else:
                response = f"I see you'd like to break it up, {customer_name}. Which of the installment plans works best?"
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
                "payment_status": "willing",
            }
    
    # ================================================================
    # PRIORITY 3: Amount range mentioned ("10-15k")
    # ================================================================
    if re.search(r'\d+\s*-\s*\d+\s*k', last_user_input.lower()):
        print(f"[NEGOTIATION] Amount range detected")
        
        range_match = re.search(r'(\d+)\s*-\s*(\d+)\s*k', last_user_input.lower())
        range_text = f"{range_match.group(1)}-{range_match.group(2)}k" if range_match else "range"
        
        ai_result = generate_negotiation_response(
            situation="amount_range_mentioned",
            customer_name=customer_name,
            outstanding_amount=amount,
            conversation_history=messages,
            last_user_input=last_user_input,
            offered_plans=offered_plans,
            context_note=f"Customer mentioned amount range: {range_text}. Need specific amount to show right plans."
        )
        
        if ai_result and ai_result.get('response'):
            response = ai_result['response']
        else:
            response = f"A range is not accepted. State one specific amount., {customer_name}?"
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
            "payment_status": "willing",
        }
    
    # ================================================================
    # PRIORITY 4: Requesting lower amount ("too high")
    # ================================================================
    if is_requesting_lower_amount(last_user_input):
        print(f"[NEGOTIATION] Customer requesting lower amount")
        
        # Find current plan if any
        current_plan = None
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                for plan in offered_plans:
                    if plan['name'] in msg.get("content", ""):
                        current_plan = plan
                        break
                if current_plan:
                    break
        
        current_index = offered_plans.index(current_plan) if current_plan and current_plan in offered_plans else -1
        has_lower_option = current_index < len(offered_plans) - 1
        
        ai_result = generate_negotiation_response(
            situation="requesting_lower_amount",
            customer_name=customer_name,
            outstanding_amount=amount,
            conversation_history=messages,
            last_user_input=last_user_input,
            offered_plans=offered_plans,
            detected_plan=current_plan['name'] if current_plan else None,
            context_note=f"Current plan: {current_plan['name'] if current_plan else 'none'}. Has lower option: {has_lower_option}"
        )
        
        if ai_result and ai_result.get('response'):
            response = ai_result['response']
        else:
            if has_lower_option:
                next_plan = offered_plans[current_index + 1]
                response = f"How about the {next_plan['name']} instead? {next_plan['description']}"
            else:
                response = f"The 6-month plan is our lowest monthly option, {customer_name}."
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
            "payment_status": "willing",
        }
    
    # ================================================================
    # PRIORITY 5: Percentage OR partial payment mentioned ("50%", "1 lakh now")
    # ================================================================
    percentage_amount = extract_percentage(last_user_input, amount)

    # Treat percentage as a partial amount
    partial_amount = None
    if percentage_amount:
        partial_amount = percentage_amount
    else:
        # Also handle explicit partial amount like "I can pay Rs X"
        explicit_amount = extract_amount(last_user_input)
        if explicit_amount and explicit_amount < amount:
            partial_amount = explicit_amount

    if partial_amount:
        print(f"[NEGOTIATION] Partial payment detected: {partial_amount}")

        response = (
            f"{customer_name}, noted.\n\n"
            f"You are offering to pay **₹{partial_amount:,.0f}**.\n\n"
            f"Any immediate payment must be completed **within 14 days** to limit further impact.\n"
            f"Please be aware that late charges continue to accumulate daily, and delaying payment "
            f"will increase your total payable amount.\n\n"
            f"Confirm the **exact date** you will make this payment so I can record it."
        )

        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
            "payment_status": "willing",
        }

    
    # ================================================================
    # PRIORITY 7: Strong negative response (STRICT SEQUENCING)
    # ================================================================
    if is_negative_response(last_user_input):
        print("[NEGOTIATION] Negative response detected")
        
        refusal_count = state.get("refusal_count", 0) + 1
        offer_stage = refusal_count
        late_per_day = 2000  # business rule

        # ------------------------------------------------
        # STEP 1 & 2 — Immediate settlement (2 HARD PUSHES)
        # ------------------------------------------------
        if offer_stage == 1:
            response = (
                f"{customer_name}, take note.\n\n"
                f"Late charges of ₹{late_per_day:,} per day are continuing to add up.\n"
                f"Immediate settlement closes this at the lowest possible amount.\n\n"
                f"Can you make the full payment today?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "refusal_count": refusal_count,
                "offer_stage": offer_stage,
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
            }

        elif offer_stage == 2:
            response = (
                f"{customer_name}, this is your final opportunity to avoid higher charges.\n\n"
                f"Delaying payment will increase your total payable and credit impact.\n"
                f"Immediate settlement today is the most cost-effective option.\n\n"
                f"Will you proceed now?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "refusal_count": refusal_count,
                "offer_stage": offer_stage,
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
            }

        # ------------------------------------------------
        # STEP 3 — 3-month plan
        # ------------------------------------------------
        elif offer_stage == 3 and len(offered_plans) >= 2:
            late_3m = late_per_day * 90
            total_3m = amount + late_3m
            plan = offered_plans[1]

            response = (
                f"{customer_name}, here is the next option.\n\n"
                f"**{plan['name']}** — {plan['description']}\n\n"
                f"Over 3 months, late charges of ₹{late_3m:,} will be added.\n"
                f"Total payable becomes **₹{total_3m:,}**.\n\n"
                f"Immediate settlement still avoids these extra charges.\n"
                f"Do you want to proceed?"
            )

            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "refusal_count": refusal_count,
                "offer_stage": offer_stage,
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
            }

        # ------------------------------------------------
        # STEP 4 — 6-month plan (FINAL OFFER)
        # ------------------------------------------------
        elif offer_stage == 4 and offered_plans:
            late_6m = late_per_day * 180
            total_6m = amount + late_6m
            plan = offered_plans[-1]

            response = (
                f"{customer_name}, this is the final option available.\n\n"
                f"**{plan['name']}** — {plan['description']}\n\n"
                f"Over 6 months, late charges of ₹{late_6m:,} will be added.\n"
                f"Total payable becomes **₹{total_6m:,}**.\n\n"
                f"Confirm if you will proceed."
            )

            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "refusal_count": refusal_count,
                "offer_stage": offer_stage,
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
            }

        # ------------------------------------------------
        # STEP 5 — ESCALATION (HARD STOP )
        # ------------------------------------------------
        else:
            response = (
                f"{customer_name}, no resolution has been reached.\n\n"
                f"This account will now be escalated.\n"
                f"Further delays may result in serious credit and recovery action."
            )

            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "refusal_count": refusal_count,
                "offer_stage": offer_stage,
                "payment_status": "callback",
                "has_escalated": True,
                "stage": "escalation",
                "awaiting_user": False,
                "is_complete": True,   
            }


    # ================================================================
    # PRIORITY 8: Reminder confirmation (WhatsApp-safe)
    # ================================================================
    if state.get("payment_status") == "callback" and state.get("callback_mode") == "reminder":
        acceptance = last_user_input.lower().strip() in ["yes", "ok", "okay", "sure", "fine"]

        if acceptance:
            ai_result = generate_negotiation_response(
                situation="reminder_confirmed",
                customer_name=customer_name,
                outstanding_amount=amount,
                conversation_history=messages,
                last_user_input=last_user_input,
                offered_plans=[],
                context_note="Customer accepted reminder. DO NOT pitch plans. Close politely."
            )

            response = (
                ai_result["response"]
                if ai_result and ai_result.get("response")
                else f"Got it, {customer_name}. I’ve scheduled a reminder for you. Please make sure to act before further charges apply."
            )

            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "call_outcome": "reminder_set",
                "stage": "negotiation",
                "awaiting_user": False,
                "is_complete": True,
            }
    # ================================================================
    # PRIORITY 8.5: Final WhatsApp confirmation & HARD STOP
    # ================================================================

    confirmation_keywords = ["whatsapp", "send"]
    affirmatives = ["yes", "sure", "okay"]

    if (
        state.get("awaiting_whatsapp_confirmation")
        and state.get("ptp_id")
        and state.get("ptp_date")
        and state.get("selected_plan")
        and (
            any(w in last_user_input.lower() for w in confirmation_keywords)
            or last_user_input.lower().strip() in affirmatives
        )
    ):
        print("[NEGOTIATION] Final WhatsApp confirmation detected — closing conversation")

        plan = state["selected_plan"]
        ptp_date = state["ptp_date"]

        response = (
            f"Thanks, {customer_name}! ✅\n\n"
            f"I’ve sent the full payment details and schedule for your **{plan['name']}** "
            f"starting on **{ptp_date}** right here on WhatsApp.\n\n"
            f"Please ensure the payment is made as scheduled to avoid further charges or escalation.\n\n"
            f"This conversation is now complete. If you need assistance later, feel free to reach out."
        )

        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "call_outcome": "ptp_recorded",
            "stage": "closing",
            "awaiting_user": False,
            "is_complete": True,
        }

    # ================================================================
    # PRIORITY 9: Check for complete commitment (plan + date)
    # ================================================================
    commitment_result = has_commitment_details(state, last_user_input)
    has_complete, committed_amount, committed_date, selected_plan = commitment_result

    if has_complete:
        print("[NEGOTIATION] ✅ Full commitment received - SAVING PTP")

        # Use plan amount if selected, otherwise use committed amount
        if selected_plan and not committed_amount:
            amount_match = re.search(r'₹(\d+(?:,\d+)*)', selected_plan['description'])
            if amount_match:
                committed_amount = float(amount_match.group(1).replace(',', ''))

        plan_name = selected_plan['name'] if selected_plan else "your payment plan"

        ptp_id = save_ptp(
            customer_id=state["customer_id"],
            amount=committed_amount,
            date=committed_date,
            plan_type=plan_name
        )

        print(f"[NEGOTIATION] PTP saved with ID: {ptp_id}")

        # 🚫 DO NOT CALL LLM HERE
        response = (
            f"Thanks, {customer_name}. ✅\n\n"
            f"I’ve recorded your commitment for the **{plan_name}** starting on "
            f"**{committed_date}**.\n\n"
            f"I’ll now send the complete payment details on WhatsApp for your confirmation."
        )

        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "ptp_amount": committed_amount,
            "ptp_date": committed_date,
            "ptp_id": ptp_id,
            "selected_plan": selected_plan,
            "awaiting_whatsapp_confirmation": True,
            "call_outcome": "ptp_recorded",
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
            "is_complete": False,  
        }

    
    # ================================================================
    # PRIORITY 10: Partial commitment - has plan but no date
    # ================================================================
    elif selected_plan and not committed_date:
        print(f"[NEGOTIATION] Plan selected but no date")
        
        ai_result = generate_negotiation_response(
            situation="plan_selected_need_date",
            customer_name=customer_name,
            outstanding_amount=amount,
            conversation_history=messages,
            last_user_input=last_user_input,
            offered_plans=offered_plans,
            detected_plan=selected_plan['name'],
            context_note=f"Plan selected: {selected_plan['name']}. Now ask for payment date."
        )
        
        if ai_result and ai_result.get('response'):
            response = ai_result['response']
        else:
            response = f"State the payment date and how the remaining balance will be cleared. Remember, your credit score is being impacted daily until this is resolved."
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "selected_plan": selected_plan,
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
        }
    

    # ================================================================
    # PRIORITY 12: Partial commitment - has date but no plan
    # ================================================================
    elif committed_date and not selected_plan and not committed_amount:
        print("[NEGOTIATION] Date provided but no plan")

        ai_result = generate_negotiation_response(
            situation="date_provided_need_plan",
            customer_name=customer_name,
            outstanding_amount=amount,
            conversation_history=messages,
            last_user_input=last_user_input,
            offered_plans=offered_plans,
            detected_date=committed_date,
            context_note="Customer provided a date but has not selected a plan. Require plan selection."
        )

        if ai_result and ai_result.get('response'):
            response = ai_result['response']
        else:
            response = (
                f"Payment date {committed_date} noted.\n\n"
                f"Select the payment plan you will commit to so this can be finalized."
            )

        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
        }

    
    # ================================================================
    # DEFAULT: General conversational response
    # ================================================================
    else:
        print("[NEGOTIATION] Using AI for general response")
        
        ai_result = generate_negotiation_response(
            situation="general_conversation",
            customer_name=customer_name,
            outstanding_amount=amount,
            conversation_history=messages,
            last_user_input=last_user_input,
            offered_plans=offered_plans,
            context_note="General negotiation conversation. Be helpful BUT firm. Mention consequences: late charges, credit damage, legal action. Guide toward IMMEDIATE commitment."
        )
        
        if ai_result and ai_result.get('response'):
            response = ai_result['response']
        else:
            # Fallback to suggesting lowest plan with urgency
            days_overdue = state.get("days_past_due", 0)
            if offered_plans and len(offered_plans) > 0:
                lowest_plan = offered_plans[-1]
                response = (
                    f"{customer_name}, we need to resolve this TODAY. Your account is {days_overdue} days overdue. "
                    f"The {lowest_plan['name']} is our most flexible option: {lowest_plan['description']} "
                    f"Can you commit to this plan right now to prevent further escalation?"
                )
            else:
                response = (
                    f"{customer_name}, I need a clear commitment from you. "
                    f"Your account is {days_overdue} days overdue and consequences are mounting. "
                    f"What specific amount and date can you commit to TODAY?"
                )
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
        }