# src/nodes/negotiation.py 

from ..state import CallState
from ..utils.llm import generate_negotiation_response, generate_payment_plans
from ..data import save_ptp
from datetime import datetime, timedelta
import re

def extract_partial_payment_offer(text: str, outstanding_amount: float) -> dict:
    """
    Detect if customer is offering partial payment.
    Returns: {
        "is_partial_offer": bool,
        "amount": float | None,
        "remaining": float | None
    }
    """
    text_lower = text.lower()
    
    # Keywords indicating partial payment
    partial_indicators = [
        "i can pay", "i can only pay", "i have", "i can give",
        "i can manage", "i can afford", "i'll pay", "i will pay"
    ]
    
    # Check if it's a partial payment offer
    if not any(indicator in text_lower for indicator in partial_indicators):
        return {"is_partial_offer": False, "amount": None, "remaining": None}
    
    # Check if they're saying "full" or "complete"
    if "full" in text_lower or "complete" in text_lower or "entire" in text_lower:
        return {"is_partial_offer": False, "amount": outstanding_amount, "remaining": 0}
    
    # Try to extract amount
    amount = extract_amount(text)
    
    if amount and amount < outstanding_amount:
        return {
            "is_partial_offer": True,
            "amount": amount,
            "remaining": outstanding_amount - amount
        }
    
    # Check for percentage
    percentage_amount = extract_percentage(text, outstanding_amount)
    if percentage_amount and percentage_amount < outstanding_amount:
        return {
            "is_partial_offer": True,
            "amount": percentage_amount,
            "remaining": outstanding_amount - percentage_amount
        }
    
    return {"is_partial_offer": False, "amount": None, "remaining": None}

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
    AI-POWERED negotiation with proper partial payment handling.
    
    Flow:
    1. If customer offers partial payment → Accept it → Ask for remaining plan
    2. Push for immediate full payment (2 times)
    3. Show 3-month plan (1 time)
    4. Show 6-month plan (1 time) 
    5. Escalate if all refused
    
    ALWAYS collect reason for delay before recording PTP.
    """
    
    # CRITICAL: Check if already escalated
    if state.get("has_escalated"):
        print("[NEGOTIATION] Already escalated - stopping")
        return {"awaiting_user": False, "is_complete": False}
    
    customer_name = state["customer_name"].split()[0]
    amount = state["outstanding_amount"]
    last_user_input = state.get("last_user_input", "")
    messages = state.get("messages", [])
    offered_plans = state.get("offered_plans", [])
    
    print(f"[NEGOTIATION] Turn, User: '{last_user_input}'")
    
    # ================================================================
    # PRIORITY 0: Check for conversation end requests
    # ================================================================
    user_lower = last_user_input.lower().strip()
    end_keywords = [
        "end convo", "end conversation", "end chat", "end call",
        "stop", "exit", "quit", 
        "goodbye", "good bye", "bye", "by",
        "i don't want to talk", "don't want to talk", "not interested anymore",
        "leave me alone", "stop calling", "stop messaging"
    ]
    
    if any(keyword in user_lower for keyword in end_keywords):
        print("[NEGOTIATION] User requested to end conversation")
        
        outstanding = state.get("outstanding_amount", 0)
        days_overdue = state.get("days_past_due", 0)
        
        # Firm closing with consequences
        response = (
            f"{customer_name}, I understand you wish to end this conversation.\n\n"
            f"However, please be aware:\n"
            f"• Your account remains {days_overdue} days overdue for ₹{outstanding:,.0f}\n"
            f"• Late charges of ₹{outstanding * 0.02:,.0f}/day continue to accumulate\n"
            f"• Your credit score is being impacted daily\n"
            f"• Legal action may be initiated if this remains unresolved\n\n"
            f"This case will be escalated. We strongly recommend making payment as soon as possible."
        )
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "payment_status": "callback",
            "callback_reason": "Customer requested to end conversation",
            "callback_reason_collected": True,
            "has_escalated": True,
            "stage": "negotiation",
            "awaiting_user": False,
            "is_complete": True,
        }
    
    # ================================================================
    # PRIORITY 1: WhatsApp confirmation (after PTP recorded)
    # ================================================================
    if state.get("awaiting_whatsapp_confirmation") and state.get("ptp_id"):
        user_lower = last_user_input.lower().strip()
        
        # Check if claiming already paid
        paid_claims = ["i paid", "already paid", "paid using", "payment done", "completed payment", "made payment", "used the link", "payment complete"]
        if any(phrase in user_lower for phrase in paid_claims):
            print("[NEGOTIATION] Customer claims payment already made")
            
            ptp_id = state["ptp_id"]
            
            response = (
                f"Thank you, {customer_name}. ✅\n\n"
                f"I'll verify the payment in our system within the next 2 hours. "
                f"If the payment is confirmed, your account will be updated immediately. "
                f"If there are any issues, we'll contact you.\n\n"
                f"Your reference number is PTP{ptp_id}.\n\n"
                f"This conversation is now complete."
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "call_outcome": "ptp_recorded_payment_claimed",
                "stage": "negotiation",
                "awaiting_user": False,
                "is_complete": True,
                "session_locked": True,
            }
        
        # Check for standard confirmations
        confirmations = ["yes", "ok", "okay", "sure", "fine", "send", "whatsapp", "got it", "received", "confirm", "confirmed"]
        
        if any(word in user_lower for word in confirmations):
            print("[NEGOTIATION] WhatsApp confirmation received - ending conversation")
            
            ptp_id = state["ptp_id"]
            ptp_amount = state["ptp_amount"]
            ptp_date = state["ptp_date"]
            plan_name = state.get("selected_plan", {}).get("name", "Payment Plan")
            
            # Generate payment link
            payment_link = f"https://abc-finance.com/pay/PTP{ptp_id}"
            
            final_message = (
                f"Perfect, {customer_name}. ✅\n\n"
                f"**Payment Confirmation:**\n"
                f"• Plan: {plan_name}\n"
                f"• Amount: ₹{ptp_amount:,.0f}\n"
                f"• Date: {ptp_date}\n"
                f"• Reference: PTP{ptp_id}\n\n"
                f"**Payment Link:** {payment_link}\n\n"
                f"Use this link to complete your payment. "
                f"Ensure payment is made by {ptp_date} to avoid escalation.\n\n"
                f"This conversation is now complete."
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": final_message}],
                "call_outcome": "ptp_recorded",
                "stage": "negotiation",
                "awaiting_user": False,
                "is_complete": True,
            }
        
        # If unclear response, use AI to understand and respond appropriately
        else:
            from ..utils.llm import generate_ai_response
            
            print("[NEGOTIATION] Using AI to handle WhatsApp confirmation response")
            
            response = generate_ai_response(
                situation="whatsapp_confirmation_followup",
                customer_name=customer_name,
                customer_message=last_user_input,
                conversation_history=messages,
                outstanding_amount=amount,
                ptp_id=state.get("ptp_id"),
                ptp_amount=state.get("ptp_amount"),
                ptp_date=state.get("ptp_date"),
                context_note=(
                    f"Customer was sent PTP confirmation with payment link. "
                    f"They responded: '{last_user_input}'. "
                    f"UNDERSTAND their response:\n"
                    f"- If they claim they paid → acknowledge and say we'll verify\n"
                    f"- If they have a question → answer it\n"
                    f"- If unclear → politely confirm they received the info\n"
                    f"Then END the conversation professionally."
                )
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "call_outcome": "ptp_recorded",
                "stage": "negotiation",
                "awaiting_user": False,
                "is_complete": True,
            }
    
    # ================================================================
    # PRIORITY 1.5: Handle callback mode partial payment responses
    # ================================================================
    if state.get("callback_mode") == "partial_payment_attempt":
        # Check if they're now willing to pay
        willing_keywords = ["yes", "i can", "i'll pay", "can pay", "will pay"]
        refusing_keywords = ["no", "can't", "cannot", "unable", "later", "next week"]
        
        if any(kw in user_lower for kw in willing_keywords):
            print("[NEGOTIATION] Customer now willing to pay during callback mode")
            # Route back through payment classification
            return {
                "callback_mode": None,
                "stage": "payment_check",
                "awaiting_user": False,
            }
        
        elif any(kw in user_lower for kw in refusing_keywords):
            print("[NEGOTIATION] Customer refuses partial payment - escalating")
            return {
                "payment_status": "callback",
                "has_escalated": True,
                "callback_reason": "Customer refused partial payment during callback request",
                "callback_reason_collected": True,
                "stage": "closing",
                "awaiting_user": False,
            }
    
    # ================================================================
    # PRIORITY 2: Reason collection (before recording PTP)
    # ================================================================
    if state.get("awaiting_reason_for_delay"):
        print("[NEGOTIATION] Collecting reason for delay")
        
        # Save the reason
        reason = last_user_input
        
        # Now record PTP with reason
        ptp_amount = state.get("pending_ptp_amount")
        ptp_date = state.get("pending_ptp_date")
        plan_name = state.get("selected_plan", {}).get("name", "Payment Plan")
        
        ptp_id = save_ptp(
            customer_id=state["customer_id"],
            amount=ptp_amount,
            date=ptp_date,
            plan_type=plan_name
        )
        
        print(f"[NEGOTIATION] ✅ PTP saved with reason: {ptp_id}")
        
        # Generate payment link
        payment_link = f"https://abc-finance.com/pay/PTP{ptp_id}"
        
        confirmation_message = (
            f"Thank you, {customer_name}. ✅\n\n"
            f"I've recorded your commitment:\n\n"
            f"• Plan: {plan_name}\n"
            f"• Amount: ₹{ptp_amount:,.0f}\n"
            f"• Date: {ptp_date}\n"
            f"• Reference: PTP{ptp_id}\n"
            f"• Reason: {reason}\n\n"
            f"**Payment Link:** {payment_link}\n\n"
            f"Please use this link to complete your payment by {ptp_date}. "
            f"Confirm once you've received this information."
        )
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": confirmation_message}],
            "ptp_amount": ptp_amount,
            "ptp_date": ptp_date,
            "ptp_id": ptp_id,
            "delay_reason": reason,
            "awaiting_whatsapp_confirmation": True,
            "awaiting_reason_for_delay": False,
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
        }
    
    # ================================================================
    # PRIORITY 3: Check for partial payment offer
    # ================================================================
    partial_check = extract_partial_payment_offer(last_user_input, amount)
    
    if partial_check["is_partial_offer"] and partial_check["amount"]:
        print(f"[NEGOTIATION] Partial payment detected: ₹{partial_check['amount']:,.0f}")
        
        partial_amount = partial_check["amount"]
        remaining = partial_check["remaining"]
        
        # Check if customer already provided date
        partial_date = extract_date(last_user_input)
        
        if not partial_date:
            # Ask for date first
            response = (
                f"Understood, {customer_name}.\n\n"
                f"You can pay ₹{partial_amount:,.0f} now.\n"
                f"Remaining balance: ₹{remaining:,.0f}\n\n"
                f"When will you make this initial payment of ₹{partial_amount:,.0f}?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "partial_payment_amount": partial_amount,
                "partial_payment_remaining": remaining,
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
            }
        else:
            # Has date - ask for reason before recording
            response = (
                f"Good, {customer_name}.\n\n"
                f"I'll record ₹{partial_amount:,.0f} to be paid on {partial_date}.\n\n"
                f"Before I finalize this, could you briefly tell me the reason for the payment delay?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "pending_ptp_amount": partial_amount,
                "pending_ptp_date": partial_date,
                "selected_plan": {"name": f"Partial Payment (₹{partial_amount:,.0f})"},
                "awaiting_reason_for_delay": True,
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
            }
    
    # ================================================================
    # PRIORITY 4: Check for complete commitment (plan + date)
    # ================================================================
    commitment_result = has_commitment_details(state, last_user_input)
    has_complete, committed_amount, committed_date, selected_plan = commitment_result
    
    if has_complete and committed_date:
        print(f"[NEGOTIATION] Full commitment detected")
        
        # Use plan amount if selected
        if selected_plan and not committed_amount:
            amount_match = re.search(r'₹(\d+(?:,\d+)*)', selected_plan['description'])
            if amount_match:
                committed_amount = float(amount_match.group(1).replace(',', ''))
        
        plan_name = selected_plan['name'] if selected_plan else "Payment Plan"
        
        # Ask for reason before recording PTP
        response = (
            f"Excellent, {customer_name}.\n\n"
            f"I'll record your commitment for **{plan_name}** starting on {committed_date}.\n\n"
            f"Before I finalize this, could you briefly tell me the reason for the payment delay?"
        )
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "pending_ptp_amount": committed_amount,
            "pending_ptp_date": committed_date,
            "selected_plan": selected_plan or {"name": plan_name},
            "awaiting_reason_for_delay": True,
            "stage": "negotiation",
            "awaiting_user": True,
            "last_user_input": None,
        }
    
    # ================================================================
    # PRIORITY 5: Strict sequencing for refusals
    # ================================================================
    
    # Detect negative responses
    if is_negative_response(last_user_input):
        print("[NEGOTIATION] Negative response detected")
        
        refusal_count = state.get("refusal_count", 0) + 1
        offer_stage = refusal_count
        late_per_day = 2000
        
        # STEP 1: Push immediate settlement (FIRST TIME)
        if offer_stage == 1:
            response = (
                f"{customer_name}, I understand you're facing difficulties.\n\n"
                f"However, your account is {state.get('days_past_due', 0)} days overdue for ₹{amount:,.0f}.\n"
                f"Late charges of ₹{late_per_day:,}/day are accumulating.\n\n"
                f"**Can you settle the full amount within 7 days to avoid further charges?**\n"
                f"This will stop all late fees immediately."
            )

        # STEP 2: Push immediate settlement (SECOND TIME - MORE URGENT)
        elif offer_stage == 2:
            response = (
                f"{customer_name}, let me be clear about the consequences:\n\n"
                f"• Your credit score is dropping daily\n"
                f"• Late charges will continue adding ₹{late_per_day:,}/day\n"
                f"• This will affect future loans, credit cards, even rentals\n\n"
                f"**I strongly recommend settling the full ₹{amount:,.0f} within this week.**\n\n"
                f"Can you commit to this?"
            )
        
        # STEP 3: Show 3-month plan
        elif offer_stage == 3:
            if not offered_plans:
                offered_plans = generate_payment_plans(amount, customer_name)
            
            plan_3month = offered_plans[1] if len(offered_plans) > 1 else offered_plans[0]
            
            response = (
                f"{customer_name}, here is an alternative option:\n\n"
                f"**{plan_3month['name']}**: {plan_3month['description']}\n\n"
                f"Note: Late charges continue over 3 months, increasing total payable.\n\n"
                f"Will you proceed with this plan?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "offered_plans": offered_plans,
                "refusal_count": refusal_count,
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
            }
        
        # STEP 4: Show 6-month plan (FINAL)
        elif offer_stage == 4:
            if not offered_plans:
                offered_plans = generate_payment_plans(amount, customer_name)
            
            plan_6month = offered_plans[-1]
            
            response = (
                f"{customer_name}, this is the final option:\n\n"
                f"**{plan_6month['name']}**: {plan_6month['description']}\n\n"
                f"Over 6 months, late charges will significantly increase your total.\n\n"
                f"Will you commit to this plan?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "offered_plans": offered_plans,
                "refusal_count": refusal_count,
                "stage": "negotiation",
                "awaiting_user": True,
                "last_user_input": None,
            }
        
        # STEP 5: Escalate
        else:
            print("[NEGOTIATION] All options refused - escalating")
            
            return {
                "refusal_count": refusal_count,
                "payment_status": "callback",
                "has_escalated": True,
                "stage": "negotiation",
                "awaiting_user": False,
            }
    
    # ================================================================
    # DEFAULT: AI handles general conversation
    # ================================================================
    print("[NEGOTIATION] Using AI for general response")
    
    ai_result = generate_negotiation_response(
        situation="general_conversation",
        customer_name=customer_name,
        outstanding_amount=amount,
        conversation_history=messages,
        last_user_input=last_user_input,
        offered_plans=offered_plans,
        context_note=(
            "Be STERN but professional. "
            "Push for commitment (amount + date). "
            "Mention consequences: late charges, credit damage."
        )
    )
    
    response = ai_result.get("response") if ai_result else (
        f"{customer_name}, immediate action is required. "
        f"Can you commit to a payment date today?"
    )
    
    return {
        "messages": state["messages"] + [{"role": "assistant", "content": response}],
        "stage": "negotiation",
        "awaiting_user": True,
        "last_user_input": None,
    }