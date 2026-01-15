"""
LLM utilities with Azure OpenAI-based intent classification and intelligent response generation.

Azure OpenAI is used for:
1. Intent classification (PRIMARY)
2. Intelligent response generation (ALL negotiation responses)
3. Payment plan generation

Rule-based patterns act as quick shortcuts for obvious cases only.
"""

from dotenv import load_dotenv
import os
from openai import AzureOpenAI
import json
import re

load_dotenv()

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

# These MUST correspond to existing nodes / flows
ALLOWED_INTENTS = [
    "paid",
    "disputed",
    "callback",
    "unable",
    "willing",
    "immediate",  # NEW: for immediate full payment
]

# ------------------------------------------------------------------
# Azure OpenAI integration (PRIMARY CLASSIFIER)
# ------------------------------------------------------------------

_client_cache = None

def get_azure_client():
    """
    Lazily initialize and cache Azure OpenAI client.
    """
    global _client_cache
    
    if _client_cache is not None:
        return _client_cache
    
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    
    if not endpoint or not api_key or not api_version:
        raise RuntimeError("Azure OpenAI credentials not set. Please set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_API_VERSION")
    
    try:
        _client_cache = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        print(f"[AZURE] âœ… Successfully initialized Azure OpenAI client")
        return _client_cache
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Azure OpenAI client: {e}")


def classify_intent_with_azure(prompt: str, context: str = "") -> str:
    """
    Use Azure OpenAI to intelligently classify customer intent.
    Returns one of the ALLOWED_INTENTS.
    
    Args:
        prompt: The user's response
        context: The question that was asked (helps with classification)
    """
    
    try:
        client = get_azure_client()
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    except Exception as e:
        print(f"Error initializing Azure OpenAI: {e}")
        return classify_intent_rule_based(prompt, context)

    # Enhanced prompt with context awareness
    llm_prompt = f"""Classify this customer response in a debt collection chat.

Question asked: "{context}"
Customer response: "{prompt}"

CRITICAL RULES:
- If asked "can you pay TODAY" and customer says "yes/okay/sure" â†’ classify as "immediate" (full payment now)
- If customer REPEATS commitment like "yes i already said that" when asked AGAIN â†’ classify as "immediate" (they're frustrated at being asked twice)

Categories (choose the best match):
- immediate: Customer agrees to pay the FULL amount TODAY/NOW (e.g., "yes" when asked "can you pay today", "I can pay now", "I'll pay today")
- willing: Customer wants to negotiate/needs payment plans OR commits to pay on a FUTURE date (e.g., "I'll pay tomorrow", "can't pay full", "installment", "payment plan", "I can pay some", "I can pay next month")
- paid: Customer claims they already made payment (e.g., "I paid", "already cleared", "payment done")
- disputed: Customer denies the debt (e.g., "never took", "not mine", "fraud", "wrong")
- callback: Customer wants to be called later WITHOUT committing to payment (e.g., "call me later", "busy now", "not a good time", "call me on [specific date]")
- unable: Customer has no money at all (e.g., "lost job", "no money", "can't afford anything")

CRITICAL RULES:
- If asked "can you pay TODAY" and customer says "yes/okay/sure" â†’ classify as "immediate" (full payment now)
- If customer says "I will pay tomorrow" or "I'll pay [future date]" â†’ classify as "willing" (future commitment, NOT callback)
- If customer says "can't pay FULL" or wants "installments" â†’ classify as "willing" (needs payment plan)
- If customer says "call me later" or "call me on [date/time]" WITHOUT mentioning payment â†’ classify as "callback"
- If customer says "busy but show me plans" â†’ classify as "willing" (wants to see options, NOT callback)
- If customer is sarcastic about paying â†’ classify as "unable"

Return ONE word only: immediate, paid, disputed, callback, unable, or willing

Classification:"""

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "You are a classification assistant. Return only one word."},
                {"role": "user", "content": llm_prompt}
            ],
            temperature=0.1,
            max_tokens=10
        )
        
        if response and response.choices and len(response.choices) > 0:
            intent = response.choices[0].message.content.strip().lower()
            
            # Validate response
            if intent in ALLOWED_INTENTS:
                return intent
            
            # Try to extract valid intent from response
            for valid_intent in ALLOWED_INTENTS:
                if valid_intent in intent:
                    return valid_intent
            
            # Fallback
            print(f"Warning: Azure returned unexpected intent '{intent}'")
            rule_intent = classify_intent_rule_based(prompt, context)
            return rule_intent if rule_intent != "unknown" else "willing"
        
        print("Warning: No response from Azure OpenAI")
        rule_intent = classify_intent_rule_based(prompt, context)
        return rule_intent if rule_intent != "unknown" else "willing"
        
    except Exception as e:
        print(f"Error in Azure OpenAI classification: {e}")
        rule_intent = classify_intent_rule_based(prompt, context)
        
        # If rule-based found something, use it
        if rule_intent != "unknown":
            return rule_intent
        
        # Smart fallback based on context
        return "willing"


# ------------------------------------------------------------------
# Rule-based intent classification (FALLBACK/SHORTCUT)
# ------------------------------------------------------------------

def classify_intent_rule_based(prompt: str, context: str = "") -> str:
    """
    Fast rule-based classification for obvious cases.
    Returns 'unknown' if uncertain - Azure will handle these.
    
    Args:
        prompt: The user's response
        context: The question that was asked
    """

    text = prompt.lower().strip()
    context_lower = context.lower()

    # Check for simple affirmative responses to "can you pay today"
    if "today" in context_lower or "able to" in context_lower:
        affirmative_immediate = ["yes", "yeah", "yep", "yup", "sure", "ok", "okay", "alright", "fine", "i can", "i will"]
        if text in affirmative_immediate or any(text.startswith(word) for word in ["yes", "yeah", "yep", "sure", "ok", "okay"]):
            # Make sure they're not saying "yes, but..." which would indicate negotiation
            if not any(word in text for word in ["but", "however", "can't", "cant", "cannot", "not", "full", "partial", "installment", "plan", "later", "discount", "if"]):
                return "immediate"

    # CRITICAL FIX: "tomorrow" with payment commitment = willing, NOT callback
    if "tomorrow" in text:
        payment_commitment_phrases = ["i will pay", "i'll pay", "will pay", "promise to pay", "can pay", "i can pay"]
        if any(phrase in text for phrase in payment_commitment_phrases):
            return "willing"  # This is a payment commitment, not a callback request

    # Very clear "already paid" signals
    if any(phrase in text for phrase in [
        "already paid", "already made payment", "already cleared",
        "payment done", "payment made", "payment cleared", "payment completed",
        "i paid", "i've paid", "i have paid", "i made payment", "i cleared",
        "paid last week", "paid yesterday", "paid today", "paid it",
        "made the payment", "cleared the payment", "settled the payment",
        "transferred", "transferred the amount", "sent the money",
        "payment was made", "payment is done", "already settled",
        "cleared my dues", "paid my dues", "settled my account",
        "i thought i paid", "just paid"
    ]):
        return "paid"

    # Very clear dispute signals
    if any(phrase in text for phrase in [
        "never took", "never borrowed", "never applied", "never had",
        "haven't taken", "havent taken", "didn't take", "didnt take",
        "not my loan", "not my account", "not my debt", "not mine",
        "don't owe", "dont owe", "do not owe", "i don't owe",
        "this is wrong", "this is incorrect", "this is not mine",
        "this is not my", "this doesn't belong", "this is fraud",
        "i didn't take", "i never took", "i never borrowed",
        "doesn't seem right", "doesnt seem right", "does not seem right",
        "not right", "seems wrong", "looks wrong", "appears wrong",
        "mistake", "error", "fraud", "fraudulent", "identity theft",
        "someone else", "wrong person", "not me", "i don't know about this",
        "i never applied", "i never signed", "unauthorized", "not authorized",
        "don't remember taking", "amount is wrong", "borrowed 30k", "only borrowed"
    ]):
        return "disputed"

    # Very clear callback signals (WITHOUT payment commitment)
    callback_without_commitment = [
        "call later", "call me later", "call back", "callback",
        "call me next week", "call me next month", "call me tomorrow",
        "call me next time", "call me some other time", "call me on",
        "call you back", "call back later", "call back tomorrow",
        "busy now", "busy right now", "busy at the moment", "busy currently",
        "not available", "not available now", "not available right now",
        "out of town", "currently out", "away", "travelling", "traveling",
        "can't talk now", "cant talk now", "cannot talk now",
        "not a good time", "bad time", "inconvenient time", "isn't a good time", "isnt a good time",
        "later please", "please call later", "call me when convenient",
        "this isn't a good time", "this isnt a good time", "can't talk about this"
    ]
    
    if any(phrase in text for phrase in callback_without_commitment):
        # Make sure it's not a payment commitment with date
        if not any(payment in text for payment in ["i will pay", "i'll pay", "can pay", "will pay"]):
            # EXCEPTION: If they also say "show me plans", it's willing, not callback
            if "show" in text and "plan" in text:
                return "willing"
            return "callback"

    # Very clear financial hardship signals
    if any(phrase in text for phrase in [
        "lost my job", "lost job", "no job", "unemployed", "jobless",
        "no money", "no funds", "no cash", "broke", "out of money",
        "can't afford", "cant afford", "cannot afford", "unable to afford",
        "financial crisis", "financial difficulty", "financial trouble",
        "struggling", "struggling financially", "going through tough times",
        "difficult situation", "hard time", "tough time",
        "no income", "no salary", "no earnings", "no source of income",
        "medical emergency", "family emergency", "emergency expenses",
        "pull money out of thin air"  # Sarcasm
    ]):
        return "unable"

    # Very clear willingness to negotiate (needs payment plans)
    if any(phrase in text for phrase in [
        "can't pay full", "cant pay full", "cannot pay full",
        "can't pay in full", "cant pay in full", "cannot pay in full",
        "can't pay the full", "cant pay the full", "cannot pay the full",
        "can't pay full amount", "cant pay full amount", "cannot pay full amount",
        "installment", "installments", "monthly payment", "monthly installments",
        "payment plan", "payemnt plan", "pay plan", "repayment plan",
        "can i pay in", "can pay in", "pay in installments", "pay in parts",
        "emi", "equated monthly installment", "monthly emi",
        "work out a plan", "work out payment", "work something out",
        "can pay partial", "can pay some", "can pay part", "can pay portion",
        "partial payment", "pay partial", "pay some", "pay part",
        "pay later", "pay next month", "pay after", "pay when",
        "let's work", "let us work", "we can work", "we can arrange",
        "interested in paying", "want to settle", "want to clear",
        "can manage", "can arrange", "can figure out", "can work something out",
        "can pay", "i can give", "i'll do the", "afford", "per month",
        "can only afford"
    ]):
        return "willing"

    return "unknown"


# ------------------------------------------------------------------
# Unified classifier (RULES â†’ AZURE)
# ------------------------------------------------------------------

def classify_intent(prompt: str, context: str = "") -> str:
    """
    Unified intent classifier.
    
    Strategy:
    1. Try fast rule-based classification for obvious cases
    2. If uncertain (unknown), use Azure OpenAI for intelligent classification
    3. Always guarantee a valid intent is returned
    
    Args:
        prompt: The user's response
        context: The question that was asked (helps with classification)
    """
    
    rule_intent = classify_intent_rule_based(prompt, context)
    
    if rule_intent in ALLOWED_INTENTS:
        print(f"[INTENT] Rule-based: {rule_intent}")
        return rule_intent
    
    print(f"[INTENT] Using Azure OpenAI for: '{prompt[:50]}...'")
    azure_intent = classify_intent_with_azure(prompt, context)
    print(f"[INTENT] Azure classified as: {azure_intent}")
    
    return azure_intent


# ------------------------------------------------------------------
# INTELLIGENT RESPONSE GENERATION (NEW - AI-POWERED)
# ------------------------------------------------------------------

def generate_negotiation_response(
    situation: str,
    customer_name: str,
    outstanding_amount: float,
    conversation_history: list = None,
    last_user_input: str = "",
    offered_plans: list = None,
    detected_plan: str = None,
    detected_date: str = None,
    detected_amount: float = None,
    context_note: str = ""
) -> dict:
    """
    Generate firm, consequence-driven debt collection responses using Azure OpenAI.
    """

    try:
        client = get_azure_client()
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")

        # Build short conversation context
        conversation_summary = ""
        if conversation_history:
            recent = conversation_history[-6:]
            conversation_summary = "\n".join(
                f"{'Agent' if m['role']=='assistant' else 'Customer'}: {m['content'][:120]}"
                for m in recent
            )

        plans_info = ""
        if offered_plans:
            plans_info = "\n".join(
                f"{i+1}. {p['name']}: {p['description']}"
                for i, p in enumerate(offered_plans)
            )

        detected_amount_str = f"Rs.{detected_amount:,.0f}" if detected_amount else "None"

        # =========================
        # STERN SYSTEM PROMPT
        # =========================
        system_prompt = f"""
You are a PROFESSIONAL DEBT COLLECTION AGENT for ABC Finance.

THIS IS A DEFAULTED LOAN CASE.

TONE REQUIREMENTS:
- Firm, direct, and authoritative
- No emojis
- No friendliness or casual language
- No empathy padding
- No apologies
- Clear consequences
- Clear urgency
- Professional but uncompromising

RESPONSE LENGTH RULES:
- MAX 2 sentences
- Prefer 1 sentence when possible
- No explanations longer than one clause
- No soft transitions (no "I understand", "I hear you")

ALWAYS EMPHASIZE:
- Debt is overdue
- Charges are increasing
- Delay increases total payable
- Immediate settlement is the lowest-risk option
- Escalation will occur if unresolved

YOU ARE NOT CUSTOMER SUPPORT.
YOU ARE COLLECTIONS.

PAYMENT CONTEXT:
Outstanding amount: Rs.{outstanding_amount:,.0f}

AVAILABLE PLANS:
{plans_info if plans_info else "Immediate settlement, 3-month, and 6-month plans apply"}

RESPONSE FORMAT (MANDATORY JSON):
{{
  "response": "Message to customer",
  "action": "continue_conversation | ask_plan | ask_date | save_ptp | escalate",
  "confidence": "high"
}}
"""

        # =========================
        # USER PROMPT
        # =========================
        user_prompt = f"""
SITUATION: {situation}

CUSTOMER LAST MESSAGE:
"{last_user_input}"

DETECTED:
- Plan: {detected_plan or "None"}
- Date: {detected_date or "None"}
- Amount: {detected_amount_str}

CONTEXT:
{context_note or "None"}

RECENT CHAT:
{conversation_summary or "No prior context"}

INSTRUCTIONS:
- Respond as a debt recovery agent
- Do NOT explain options unless explicitly asked
- Push for immediate settlement first
- State consequences clearly
- Push immediate settlement unless already committed
- If delaying, explain cost of delay numerically
- Ask at most ONE direct question if required

Generate response now.
"""

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=180,
        )

        text = response.choices[0].message.content.strip()

        # Extract JSON
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        # Hard fallback
        return {
            "response": (
            f"Your account remains overdue on Rs.{outstanding_amount:,.0f}. "
            f"Charges are increasing daily. Confirm if you are proceeding with payment today."
        ),  
            "action": "continue_conversation",
            "confidence": "high",
        }

    except Exception as e:
        print(f"[AI RESPONSE ERROR] {e}")
        return {
            "response": (
                f"{customer_name}, your outstanding balance of Rs.{outstanding_amount:,.0f} remains unpaid. "
                f"Charges are accumulating daily. Immediate settlement is required to prevent escalation."
            ),
            "action": "continue_conversation",
            "confidence": "high",
        }


# ------------------------------------------------------------------
# Payment plan generation (EXISTING)
# ------------------------------------------------------------------

def generate_payment_plans(outstanding_amount: float, customer_name: str) -> list:
    """
    Generate 2-3 payment plan options using Azure OpenAI.
    Falls back to rule-based plans if Azure fails.
    """
    
    try:
        client = get_azure_client()
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
        
        prompt = f"""Create 3 payment plans for a debt of Rs.{outstanding_amount:,.0f}.

Return ONLY a JSON array with this exact structure:
[
  {{"name": "Immediate Settlement", "description": "Pay full amount with 5% discount within 7 days: Rs.{int(outstanding_amount * 0.95):,}"}},
  {{"name": "3-Month Installment", "description": "Pay in 3 monthly installments of Rs.{int(outstanding_amount / 3):,} each"}},
  {{"name": "6-Month Installment", "description": "Pay in 6 monthly installments of Rs.{int(outstanding_amount / 6):,} each"}}
]

Return only the JSON array, nothing else."""

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "You are a financial assistant. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        if response and response.choices and len(response.choices) > 0:
            text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                plans = json.loads(json_str)
                
                if isinstance(plans, list) and len(plans) > 0:
                    for plan in plans:
                        if 'name' not in plan or 'description' not in plan:
                            raise Exception("Invalid plan structure")
                    
                    print(f"[PLANS] Generated {len(plans)} payment plans using Azure")
                    return plans
        
        raise Exception("Could not extract valid JSON from Azure response")
        
    except Exception as e:
        print(f"Error generating payment plans with Azure: {e}")
        return generate_fallback_plans(outstanding_amount)


def generate_fallback_plans(amount: float) -> list:
    """
    Generate fallback payment plans using rule-based logic.
    """
    
    plans = []
    
    # Plan 1: Full payment with 5% discount within 7 days
    discount = int(amount * 0.05)
    plans.append({
        "name": "Immediate Settlement",
        "description": f"Pay Rs.{amount - discount:,.0f} (5% discount) in full within 7 days"
    })
    
    # Plan 2: 3-month installment
    monthly_3 = int(amount / 3)
    plans.append({
        "name": "3-Month Installment",
        "description": f"Pay Rs.{monthly_3:,.0f} per month for 3 months"
    })
    
    # Plan 3: 6-month installment
    monthly_6 = int(amount / 6)
    plans.append({
        "name": "6-Month Installment",
        "description": f"Pay Rs.{monthly_6:,.0f} per month for 6 months"
    })
    
    print(f"[PLANS] Using fallback plans ({len(plans)} options)")
    return plans

# ------------------------------------------------------------------
# AI Response Generator (NEW - for non-negotiation responses)
# ------------------------------------------------------------------

def generate_ai_response(
    situation: str,
    customer_name: str,
    customer_message: str = "",
    conversation_history: list[dict] = None,
    outstanding_amount: float = None,
    days_overdue: int = None,
    context_note: str = "",
    **kwargs
) -> str:
    """
    Generate AI response for ANY situation outside of negotiation.
    
    Used for: closing messages, paid verification, etc.
    
    Args:
        situation: What's happening (e.g., "ask_transaction_proof", "closing_callback")
        customer_name: Customer's first name
        customer_message: What customer just said
        conversation_history: Recent conversation messages
        outstanding_amount: Debt amount
        days_overdue: Days past due
        context_note: Additional instructions for AI
        **kwargs: Any other context (ptp_id, transaction_id, etc.)
    
    Returns:
        AI-generated response string
    """
    
    try:
        client = get_azure_client()
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    except Exception as e:
        print(f"[ERROR] Azure client failed: {e}")
        # Minimal fallback
        return f"I understand, {customer_name}. Let me help you with this."
    
    # Build context string
    context_parts = []
    if outstanding_amount is not None:
        context_parts.append(f"Outstanding: Rs.{outstanding_amount:,.0f}")
    if days_overdue is not None:
        context_parts.append(f"{days_overdue} days overdue")
    
    # Add any kwargs to context
    for key, value in kwargs.items():
        if value is not None:
            context_parts.append(f"{key}: {value}")
    
    context_str = ", ".join(context_parts) if context_parts else "No specific context"
    
    # Build conversation history
    history_str = ""
    if conversation_history:
        recent = conversation_history[-6:]  # Last 6 messages
        for msg in recent:
            role = "Agent" if msg.get("role") == "assistant" else "Customer"
            content = msg.get("content", "")[:150]  # Truncate long messages
            history_str += f"{role}: {content}\n"
    
    # Create comprehensive prompt
    system_prompt = """You are a professional debt collection agent. Your responses should be:

1. FIRM but professional - apply pressure appropriately
2. CONSEQUENCE-FOCUSED - mention late charges, credit score impact, legal action when relevant
3. DIRECT and professional - no friendliness
4. SPECIFIC - use actual numbers, dates, amounts when provided
5. ACTION-ORIENTED - guide customer toward resolution TODAY

Key phrases to use when appropriate:
- "Your credit score is being impacted right now"
- "Late charges of Rs.X/day are accumulating"
- "Legal action may be initiated within 7 days"
- "This will affect your ability to get loans, jobs, or rentals"
- "I need a specific date/amount"
- "Time is critical"

NEVER use: "no worries", excessive emojis, overly apologetic language."""

    user_prompt = f"""Generate a response for this situation.

Situation: {situation}
Customer: {customer_name}
Context: {context_str}

Customer just said: "{customer_message}"

Recent conversation:
{history_str}

Additional instructions:
{context_note}

Generate your response. Be firm, professional, and consequence-focused. Keep it natural and conversational.

Respond with ONLY the agent's message, no labels or preamble."""

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=400
        )
        
        ai_response = response.choices[0].message.content.strip()
        print(f"[AI] Generated response for: {situation}")
        return ai_response
        
    except Exception as e:
        print(f"[ERROR] AI response generation failed: {e}")
        # Minimal fallback
        return f"I understand, {customer_name}. Let me help you resolve this. Can you tell me more about your situation?"