# src/nodes/negotiation.py 

from ..state import CallState
from ..utils.llm import generate_negotiation_response, generate_payment_plans
from ..data import save_ptp
from datetime import datetime, timedelta
import re

def classify_user_intent(last_user_input: str, messages: list, state: CallState) -> dict:
    """
    Classify what the user is trying to communicate.
    Returns: {
        "intent": str,  # One of: partial_payment, cant_pay_full, rejection, acceptance, providing_amount, providing_date, stalling
        "confidence": float,
        "reasoning": str
    }
    """
    from ..utils.llm import get_azure_client
    
    # Format recent conversation for context
    recent_messages = messages[-6:] if len(messages) > 6 else messages
    conversation_context = "\n".join([
        f"{'Agent' if msg['role'] == 'assistant' else 'Customer'}: {msg['content']}"
        for msg in recent_messages
    ])
    
    prompt = f"""You are analyzing a debt collection conversation to understand the customer's intent.

Conversation context:
{conversation_context}

Customer's latest message: "{last_user_input}"

Outstanding amount: Rs.{state.get('outstanding_amount', 0):,.0f}
Partial payment offered: {"Rs." + str(state.get('partial_payment_amount', 0)) if state.get('partial_payment_amount') else "None"}

Classify the customer's intent as ONE of these:
1. partial_payment - Customer wants to pay SOME amount today and rest later
2. cant_pay_full - Customer explicitly states they CANNOT pay the full amount today
3. rejection - Customer is rejecting the current offer/plan
4. acceptance - Customer is accepting/agreeing to current offer
5. providing_amount - Customer is stating a specific payment amount
6. providing_date - Customer is giving a payment date/timeframe
7. stalling - Customer is being vague or avoiding commitment
8. query - Customer is asking a question

Return ONLY a JSON object in this exact format:
{{"intent": "one_of_above", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""

    try:
        client = get_azure_client()
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        import json
        result = json.loads(result_text)
        
        print(f"[INTENT] Classified as '{result['intent']}' with confidence {result['confidence']}")
        return result
        
    except Exception as e:
        print(f"[INTENT] Classification failed: {e}")
        # Fallback to basic keyword matching
        text_lower = last_user_input.lower()
        if any(word in text_lower for word in ["some", "part", "partial"]) and "today" in text_lower:
            return {"intent": "partial_payment", "confidence": 0.7, "reasoning": "fallback"}
        elif "can't pay" in text_lower or "cannot pay" in text_lower:
            return {"intent": "cant_pay_full", "confidence": 0.7, "reasoning": "fallback"}
        elif any(word in text_lower for word in ["no", "not interested", "none"]):
            return {"intent": "rejection", "confidence": 0.6, "reasoning": "fallback"}
        else:
            return {"intent": "stalling", "confidence": 0.5, "reasoning": "fallback"}

def detect_partial_payment_scenario(state: CallState, last_user_input: str) -> dict:
    """
    Detect if customer is offering to pay partial amount today + rest in installments.
    Returns: {
        "is_partial": bool,
        "amount_today": float | None,
        "remaining": float | None
    }
    """
    text_lower = last_user_input.lower()
    outstanding = state.get("outstanding_amount", 0)
    
    # Check for partial payment indicators
    partial_indicators = [
        "today and", "now and", "and the rest", "and rest",
        "partial", "some now", "pay part"
    ]
    
    if not any(indicator in text_lower for indicator in partial_indicators):
        return {"is_partial": False, "amount_today": None, "remaining": None}
    
    # Extract the amount customer can pay today
    amount = extract_amount(last_user_input)
    
    if amount and amount < outstanding:
        return {
            "is_partial": True,
            "amount_today": amount,
            "remaining": outstanding - amount
        }
    
    return {"is_partial": False, "amount_today": None, "remaining": None}

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
    Handles:
    - Commas: 100,000
    - Indian numbering: lakh, crore
    - K notation: 100k
    - Various numeric formats
    """
    if not text:
        return None
        
    text_lower = text.lower().strip()
        
    # Remove currency symbols
    text_clean = text_lower.replace('rs', '').replace('₹', '').strip()
        
    # Handle "lakh" and "crore" (Indian numbering)
    if 'lakh' in text_clean or 'lac' in text_clean:
        # Extract the number before "lakh"
        lakh_pattern = r'(\d+(?:\.\d+)?)\s*(?:lakh|lac)'
        match = re.search(lakh_pattern, text_clean)
        if match:
            num = float(match.group(1))
            amount = num * 100000
            print(f"[AMOUNT] Extracted from lakh notation: Rs.{amount:,.0f}")
            return amount
            
    if 'crore' in text_clean or 'cr' in text_clean:
        # Extract the number before "crore"
        crore_pattern = r'(\d+(?:\.\d+)?)\s*(?:crore|cr)'
        match = re.search(crore_pattern, text_clean)
        if match:
            num = float(match.group(1))
            amount = num * 10000000
            print(f"[AMOUNT] Extracted from crore notation: Rs.{amount:,.0f}")
            return amount
            
    # Handle 'k' notation (100k = 100000)
    if 'k' in text_clean:
        k_pattern = r'(\d+(?:\.\d+)?)\s*k'
        match = re.search(k_pattern, text_clean)
        if match:
            amount = float(match.group(1)) * 1000
            if 100 < amount < 10000000:
                print(f"[AMOUNT] Extracted from 'k' notation: Rs.{amount:,.0f}")
                return amount
                
    # Remove commas and extract pure number
    text_clean = text_clean.replace(',', '').replace(' ', '')
        
    # Try to extract a standalone number
    number_pattern = r'(\d+(?:\.\d+)?)'
    match = re.search(number_pattern, text_clean)
    
    if match:
        amount = float(match.group(1))
        if 100 < amount < 10000000:  # Reasonable range
            print(f"[AMOUNT] Extracted standalone number: Rs.{amount:,.0f}")
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
            print(f"[AMOUNT] Calculated {percentage}% of Rs.{total_amount:,.0f} = Rs.{amount:,.0f}")
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
    - Skip "3 month plan" -> don't extract "3" as date
    - Skip "10-15k" -> don't extract "10" as date
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
                    amount_match = re.search(r'Rs.(\d+(?:,\d+)*)', selected_plan['description'])
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
                                amount_match = re.search(r'Rs.(\d+(?:,\d+)*)', plan['description'])
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
                                amount_match = re.search(r'Rs.(\d+(?:,\d+)*)', selected_plan['description'])
                                if amount_match:
                                    committed_amount = float(amount_match.group(1).replace(',', ''))
                                break
                
            
            # Check for plan change if plan already selected
            if selected_plan:
                new_plan = detect_plan_change(content, selected_plan, offered_plans)
                if new_plan:
                    selected_plan = new_plan
                    amount_match = re.search(r'Rs.(\d+(?:,\d+)*)', new_plan['description'])
                    if amount_match:
                        committed_amount = float(amount_match.group(1).replace(',', ''))
                        print(f"[PLAN CHANGE] Updated amount: Rs.{committed_amount:,.0f}")
            
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
    AI-POWERED negotiation logic.
    Replaces hardcoded heuristics with LLM-driven flow control.
    """
    
    # 1. Escalation check
    if state.get("has_escalated"):
        return {"awaiting_user": False, "is_complete": False}
        
    customer_name = state["customer_name"].split()[0]
    amount = state["outstanding_amount"]
    last_user_input = state.get("last_user_input", "")
    messages = state.get("messages", [])
    
    # 2. WhatsApp Confirmation (FINALIZE PTP HERE)
    if state.get("awaiting_whatsapp_confirmation"):
        user_input = last_user_input.lower().strip()

        if any(w in user_input for w in ["yes", "ok", "sure", "fine", "confirm", "received"]):
            return {
                # 🔒 FINALIZE PAYMENT COMMITMENT
                "payment_status": "ptp_confirmed",

                # Persist final PTP
                "ptp_id": state.get("ptp_id"),
                "ptp_amount": state.get("ptp_amount"),
                "ptp_date": state.get("ptp_date"),

                # Clear transient PTP state
                "pending_ptp_amount": None,
                "pending_ptp_date": None,

                # Conversation control
                "awaiting_whatsapp_confirmation": False,
                "awaiting_user": False,

                # Close session cleanly
                "is_complete": True,
                "call_outcome": "ptp_confirmed",
                "stage": "closing",
            }

        else:
            return {
                "messages": state["messages"] + [{
                    "role": "assistant",
                    "content": "Please reply with 'Yes' to confirm receipt of the payment link."
                }],
                "awaiting_user": True,
                "stage": "negotiation"
            }

    # 3. PARTIAL PAYMENT DETECTION (NEW - handles "100k today + rest in plans")
    partial_info = detect_partial_payment_scenario(state, last_user_input)
    
    if partial_info["is_partial"]:
        amount_today = partial_info["amount_today"]
        remaining = partial_info["remaining"]
        
        print(f"[PARTIAL PAYMENT] Customer offers Rs.{amount_today:,.0f} today, Rs.{remaining:,.0f} remaining")
        
        # Ask when they'll pay the partial amount TODAY
        response = (
            f"I understand you can pay Rs.{amount_today:,.0f} today.\n\n"
            f"When exactly will you make this payment today? "
            f"Please note: Late charges of Rs.{amount * 0.02:,.0f}/day continue to accrue until full settlement."
        )
        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "partial_payment_amount": amount_today,
            "partial_payment_remaining": remaining,
            "payment_status": "willing",
            "awaiting_user": True,
            "stage": "negotiation"
        }
    
    # 3.5 VAGUE PARTIAL PAYMENT ("some amount today")
    if not partial_info["is_partial"]:
        # Check if user mentions paying "some" or "part" without specific amount
        vague_partial_indicators = [
            "some amount", "some money", "part of", "partial payment",
            "pay part", "pay some", "something today"
        ]
        if any(indicator in last_user_input.lower() for indicator in vague_partial_indicators):
            print(f"[PARTIAL PAYMENT] Vague offer detected, asking for specific amount")
            
            response = (
                f"How much can you pay today, {customer_name}? "
                f"Please provide a specific amount so I can calculate the remaining balance."
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "payment_status": "willing",
                "awaiting_partial_amount_clarification": True,
                "awaiting_user": True,
                "stage": "negotiation"
            }

    # 4. Reason Collection Logic (CRITICAL: Must remain)
    if state.get("awaiting_reason_for_delay"):
        # Clean up the input for checking
        cleaned_input = last_user_input.strip().lower() if last_user_input else ""
        cleaned_input = cleaned_input.replace(",", "").replace(".", "")
        # Check if it's a non-answer (just agreement without actual reason)
        non_answers = ["yes", "ok", "okay", "sure", "fine", "i can pay today",
                        "i can pay", "ill pay", "i will pay", "i can", "i will"]
        is_non_answer = not last_user_input or any(
            cleaned_input == na or cleaned_input.startswith(na + " ") 
            for na in non_answers
        )
        if is_non_answer:
            return {
                "messages": state["messages"] + [{
                    "role": "assistant",
                    "content": "Please let me know the reason for the delay in payment."
                }],
                "awaiting_user": True,
                "stage": "negotiation"
            }

        reason = last_user_input.strip()

            
        # Record the reason and finalize PTP
        reason = last_user_input
        ptp_amount = state.get("pending_ptp_amount")
        ptp_date = state.get("pending_ptp_date")
        selected_plan = state.get("selected_plan") or {}
        plan_name = selected_plan.get("name", "Payment Plan")
        
        ptp_id = save_ptp(
            customer_id=state["customer_id"],
            amount=ptp_amount,
            date=ptp_date,
            plan_type=plan_name
        )
        
        payment_link = f"https://abc-finance.com/pay/PTP{ptp_id}"
        
        confirmation_message = (
            f"Thank you, {customer_name}. ✅\n\n"
            f"I've recorded your commitment:\n"
            f"- Plan: {plan_name}\n"
            f"- Amount: Rs.{ptp_amount:,.0f}\n"
            f"- Date: {ptp_date}\n"
            f"- Reason: {reason}\n\n"
            f"**Payment Link:** {payment_link}"
        )

        
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": confirmation_message}],
            "ptp_amount": ptp_amount,
            "ptp_date": ptp_date,
            "ptp_id": ptp_id,
            "delay_reason": reason,
            "awaiting_whatsapp_confirmation": False,
            "awaiting_reason_for_delay": False,
            "stage": "negotiation",
            "awaiting_user": True
        }
    
    # 4.5 COLLECTING PARTIAL AMOUNT (user responded with amount)
    if state.get("awaiting_partial_amount_clarification"):
        # extract_amount is already defined above in this file
        
        amount_offered = extract_amount(last_user_input)
        
        if amount_offered and amount_offered < amount:
            print(f"[PARTIAL AMOUNT] User specified Rs.{amount_offered:,.0f}")
            
            remaining = amount - amount_offered
            
            # Now ask about payment plan for remaining
            response = (
                f"I can accept Rs.{amount_offered:,.0f} as partial payment today.\n\n"
                f"For the remaining Rs.{remaining:,.0f}, I can offer:\n"
                f"• Immediate settlement: Pay within 7 days with 5% discount (Rs.{remaining * 0.95:,.0f})\n\n"
                f"When can you pay the remaining amount?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "partial_payment_amount": amount_offered,
                "partial_payment_remaining": remaining,
                "awaiting_partial_amount_clarification": False,
                "payment_status": "willing",
                "awaiting_user": True,
                "stage": "negotiation"
            }
        else:
            # Didn't extract valid amount or amount >= outstanding
            response = f"Please provide a specific numeric amount you can pay today."
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "awaiting_user": True,
                "stage": "negotiation"
            }

    # 5. INTENT CLASSIFICATION - Understand what user is saying
    user_intent = classify_user_intent(last_user_input, messages, state)
    intent = user_intent.get("intent")
    
    print(f"[NEGOTIATION FLOW] Intent: {intent}, Stage: {state.get('stage')}")
    
    # Get negotiation stage tracking (add to state if not present)
    immediate_settlement_stage = state.get("immediate_settlement_stage", 0)  # 0, 1, 2
    installment_stage = state.get("installment_stage", 0)  # 0, 1 (3-month), 2 (6-month)
    
    # 6. ROUTE BASED ON INTENT
    
    # SCENARIO 1: User wants to pay PARTIAL amount today
    if intent == "partial_payment" and not state.get("partial_payment_amount"):
        # Ask for specific amount
        response = f"How much can you pay today, {customer_name}? Please provide a specific amount."
        return {
            "messages": state["messages"] + [{"role": "assistant", "content": response}],
            "awaiting_user": True,
            "stage": "negotiation"
        }
    
    # SCENARIO 2: User CAN'T pay full amount today
    if intent == "cant_pay_full":
        # Progressive pushing: immediate settlement → 3-month → 6-month → escalate
        
        if immediate_settlement_stage == 0:
            # First push: Offer immediate settlement with 5% discount
            discounted = amount * 0.95
            response = (
                f"I understand, {customer_name}. Your debt is overdue and charges are increasing daily, "
                f"raising your total payable. Immediate settlement of Rs.{discounted:,.0f} within 7 days "
                f"with 5% discount is your lowest-risk option.\n\n"
                f"This stops all further charges. Can you commit to this payment?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "immediate_settlement_stage": 1,
                "awaiting_user": True,
                "stage": "negotiation"
            }
            
        elif immediate_settlement_stage == 1:
            # Second push: Emphasize consequences
            discounted = amount * 0.95
            response = (
                f"Refusing immediate payment increases your total due as charges continue to accrue. "
                f"Late charges of Rs.{amount * 0.02:,.0f}/day are being added.\n\n"
                f"Immediate settlement of Rs.{discounted:,.0f} within 7 days is your lowest-risk option. "
                f"Will you commit to this now?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "immediate_settlement_stage": 2,
                "awaiting_user": True,
                "stage": "negotiation"
            }
            
        elif installment_stage == 0:
            # Show 3-month plan
            monthly_3 = amount / 3
            response = (
                f"I understand immediate payment is difficult. Let me offer an installment option:\n\n"
                f"**3-Month Installment Plan:**\n"
                f"Pay Rs.{monthly_3:,.0f} per month for 3 months\n\n"
                f"This will help you manage the payment. Can you commit to this plan?"
            )
            
            plans = [{
                "name": "3-Month Installment",
                "description": f"Pay Rs.{monthly_3:,.0f} per month for 3 months"
            }]
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "offered_plans": plans,
                "installment_stage": 1,
                "awaiting_user": True,
                "stage": "negotiation"
            }
            
        elif installment_stage == 1:
            # Show 6-month plan
            monthly_6 = amount / 6
            response = (
                f"Let me offer a more flexible option:\n\n"
                f"**6-Month Installment Plan:**\n"
                f"Pay Rs.{monthly_6:,.0f} per month for 6 months\n\n"
                f"This gives you more time. Can you commit to this plan?"
            )
            
            plans = [{
                "name": "6-Month Installment",
                "description": f"Pay Rs.{monthly_6:,.0f} per month for 6 months"
            }]
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "offered_plans": plans,
                "installment_stage": 2,
                "awaiting_user": True,
                "stage": "negotiation"
            }
            
        else:
            # Escalate
            response = (
                f"I understand you're unable to commit to any payment plan at this time. "
                f"Since no plan was chosen, we will have to escalate this matter. "
                f"Our senior team will contact you within 24 hours to discuss further steps.\n\n"
                f"Reference ID: {state.get('customer_id')}"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "has_escalated": True,
                "is_complete": True,
                "call_outcome": "escalated",
                "escalation_reason": "No payment plan accepted",
                "stage": "negotiation",
                "awaiting_user": False
            }
    
    # SCENARIO 3: User is rejecting current offer
    if intent == "rejection":
        # Progress to next stage based on current position
        if immediate_settlement_stage < 2:
            # Still pushing immediate settlement
            immediate_settlement_stage += 1
            discounted = amount * 0.95
            response = (
                f"I understand your concern. However, delay increases your total payable significantly. "
                f"Immediate settlement of Rs.{discounted:,.0f} within 7 days with 5% discount "
                f"avoids further charges. Will you commit to this now?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "immediate_settlement_stage": immediate_settlement_stage,
                "awaiting_user": True,
                "stage": "negotiation"
            }
        elif installment_stage == 0:
            # Move to 3-month plan
            monthly_3 = amount / 3
            response = (
                f"Let me offer an installment option to make this easier:\n\n"
                f"**3-Month Installment Plan:**\n"
                f"Pay Rs.{monthly_3:,.0f} per month for 3 months\n\n"
                f"Can you commit to this?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "installment_stage": 1,
                "awaiting_user": True,
                "stage": "negotiation"
            }
        elif installment_stage == 1:
            # Move to 6-month plan
            monthly_6 = amount / 6
            response = (
                f"**6-Month Installment Plan:**\n"
                f"Pay Rs.{monthly_6:,.0f} per month for 6 months\n\n"
                f"This is our most flexible option. Can you commit?"
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "installment_stage": 2,
                "awaiting_user": True,
                "stage": "negotiation"
            }
        else:
            # Escalate
            response = (
                f"Since no plan was chosen, we will have to escalate this matter. "
                f"Someone will contact you within 24 hours to discuss further steps."
            )
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response}],
                "has_escalated": True,
                "is_complete": True,
                "call_outcome": "escalated",
                "stage": "negotiation",
                "awaiting_user": False
            }
    
    # SCENARIO 4: User accepts
    if intent == "acceptance":
        # Check if we have amount and date
        has_complete, committed_amount, committed_date, selected_plan = has_commitment_details(state, last_user_input)
        
        if not committed_date:
            return {
                "messages": state["messages"] + [{
                    "role": "assistant",
                    "content": "When would you like to make this payment?"
                }],
                "pending_ptp_amount": committed_amount or amount,
                "awaiting_user": True,
                "stage": "negotiation"
            }
        
        # Have both amount and date - save PTP
        return {
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": "Thank you. Before I proceed, may I know the reason for the delay in payment?"
            }],
            "pending_ptp_amount": committed_amount or amount,
            "pending_ptp_date": committed_date,
            "awaiting_reason_for_delay": True,
            "awaiting_user": True,
            "stage": "negotiation"
        }
    
    # FALLBACK: Use LLM for other cases
    ai_result = generate_negotiation_response(
        situation="negotiation",
        customer_name=customer_name,
        outstanding_amount=amount,
        conversation_history=messages,
        last_user_input=last_user_input,
        offered_plans=state.get("offered_plans")
    )
    
    message = ai_result.get("response")
    
    return {
        "messages": state["messages"] + [{"role": "assistant", "content": message}],
        "awaiting_user": True,
        "stage": "negotiation"
    }
    
