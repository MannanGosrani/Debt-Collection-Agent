# src/utils/llm.py

"""
LLM utilities with Azure OpenAI-based intent classification and intelligent response generation.

Azure OpenAI is used for:
1. Structured payment intent decisions (JSON actions)
2. Negotiation response generation
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
        print(f"[AZURE] ✅ Successfully initialized Azure OpenAI client")
        return _client_cache
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Azure OpenAI client: {e}")

# =========================
# CANONICAL PAYMENT INTENT ENGINE
# =========================
# This is the ONLY function allowed to decide payment intent.
# Do NOT add rule-based or free-form intent detection elsewhere.

def decide_payment_intent(
    user_message: str,
    state_snapshot: dict
) -> dict:
    """
    Single LLM-driven payment intent decision engine.

    Returns a SAFE dict:
    {
        "intent": str,
        "date": str | None,
        "can_pay_now": float | None
    }

    This function:
    - NEVER throws
    - NEVER mutates state
    - NEVER guesses missing info
    """

    client = None
    try:
        client = get_azure_client()
    except Exception:
        return {
            "intent": "UNKNOWN",
            "date": None,
            "can_pay_now": None,
        }

    system_prompt = """
You are a debt collection decision engine.

Analyze the customer's message and determine their payment intent.

Return ONLY valid JSON. No explanations.

INTENTS (choose exactly one):
- AGREE_TO_PAY
- ALREADY_PAID
- CANNOT_PAY_FULL
- CALLBACK_REQUEST
- DISPUTE
- UNKNOWN

RULES:
- If customer agrees to pay now or today → AGREE_TO_PAY
- If customer claims payment already made → ALREADY_PAID
- If customer offers partial payment → CANNOT_PAY_FULL
- If customer asks to pay later or call back → CALLBACK_REQUEST
- If customer denies the debt → DISPUTE
- If unclear → UNKNOWN

Do NOT invent dates or amounts.

OUTPUT JSON FORMAT:
{
  "intent": "<INTENT>",
  "date": "DD-MM-YYYY or null",
  "can_pay_now": number or null
}
"""

    user_prompt = f"""
Customer message:
"{user_message}"

Context:
Outstanding amount: {state_snapshot.get("outstanding_amount")}
Days past due: {state_snapshot.get("days_past_due")}
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=150,
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        return {
            "intent": parsed.get("intent", "UNKNOWN"),
            "date": parsed.get("date"),
            "can_pay_now": parsed.get("can_pay_now"),
        }

    except Exception:
        return {
            "intent": "UNKNOWN",
            "date": None,
            "can_pay_now": None,
        }


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
        # ENHANCED SYSTEM PROMPT (MANDATORY WORKFLOW)
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

=== CRITICAL ACTION RULES (FOLLOW EXACTLY) ===

You MUST choose ONE of these actions in your JSON response:

ACTION 1: "save_ptp"
WHEN TO USE:
✓ Customer says: "yes", "okay", "ok", "sure", "fine", "i can pay", "i'll pay", "i will pay"
✓ Customer agrees to make payment today or soon
✓ You have confirmed they want to proceed with payment

WHAT HAPPENS NEXT:
→ System will AUTOMATICALLY ask: "What was the reason for the delay in payment?"
→ You do NOT ask for the reason yourself
→ You just acknowledge briefly

EXAMPLES:
User: "yes, i can pay today"
Your JSON: {{"action": "save_ptp", "response": "Thank you for confirming."}}

User: "okay fine"
Your JSON: {{"action": "save_ptp", "response": "Thank you, Mannan."}}

User: "sure, i'll pay"
Your JSON: {{"action": "save_ptp", "response": "Acknowledged."}}

⚠️ NEVER FINALIZE PAYMENT WITHOUT "save_ptp" ACTION FIRST ⚠️

---

ACTION 2: "ask_date"
WHEN TO USE:
✓ Customer committed to pay but didn't mention when
✓ You need a specific payment date

EXAMPLE:
Your JSON: {{"action": "ask_date", "response": "When can you make this payment?"}}

---

ACTION 3: "ask_plan"
WHEN TO USE:
✓ Customer wants installment options
✓ Customer says "I can't pay full amount"
✓ Customer asks about payment plans

EXAMPLE:
Your JSON: {{"action": "ask_plan", "response": "I can offer you 3 options: immediate settlement, 3-month, or 6-month installments."}}

---

ACTION 4: "escalate"
WHEN TO USE:
✓ Customer refuses to pay after multiple attempts
✓ Customer is hostile or abusive
✓ No progress after 3+ exchanges

EXAMPLE:
Your JSON: {{"action": "escalate", "response": "I will escalate this to our legal team."}}

---

ACTION 5: "continue_conversation"
WHEN TO USE:
✓ Customer asking questions about the debt
✓ Clarification needed
✓ Any other situation not covered above

EXAMPLE:
Your JSON: {{"action": "continue_conversation", "response": "Your debt is from your Home Loan account."}}

=== THE CRITICAL WORKFLOW ===

Step 1: Customer agrees → You return: action "save_ptp"
Step 2: System automatically asks for delay reason (not you!)
Step 3: Customer provides actual reason ("I lost my job", etc.)
Step 4: System finalizes PTP and sends link

⚠️ IMPORTANT ⚠️
- "yes, i can pay today" is a COMMITMENT, not a delay reason
- ALWAYS use "save_ptp" when customer agrees
- Do NOT skip this step
- Do NOT ask for reason yourself

RESPONSE FORMAT (STRICT JSON):
{{
  "response": "Your message to customer",
  "action": "save_ptp | ask_date | ask_plan | escalate | continue_conversation",
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

SITUATION-SPECIFIC RESPONSES:

For "verify_payment_details" or "ask_payment_proof":
- Customer has claimed they already paid OR provided transaction ID/proof
- YOUR RESPONSE MUST:
  * Acknowledge receipt of the information
  * State you will verify it with the records
  * Mention timeline (24-48 hours)
  * Be brief (2-3 sentences max)
  * DO NOT mention late charges or legal action
  * Example: "Thank you, [name]. I'll verify this payment from our side and get back to you shortly. You should receive confirmation within 24 hours."

For "ask_transaction_proof":
- Customer claims payment made but hasn't provided proof yet
- Ask firmly for transaction ID, date, and amount
- Emphasize urgency and consequences of delay

For all other situations:
- Use pressure tactics appropriately
- Mention consequences

Key phrases to use when appropriate (NOT for payment verification):
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
    
# ------------------------------------------------------------------
# PAYMENT VERIFICATION DECISION ENGINE (NEW)
# ------------------------------------------------------------------

def decide_payment_verification(user_message: str) -> dict:
    """
    Decide whether the customer has provided valid payment proof.

    Returns SAFE dict:
    {
        "verification_result": "HAS_PROOF" | "NO_PROOF" | "UNAUTHORIZED" | "UNCLEAR"
    }

    GUARANTEES:
    - NEVER throws
    - NEVER mutates state
    - NEVER infers missing facts
    """
    
    # RULE-BASED FALLBACK: Check for obvious proof indicators
    user_lower = user_message.lower()
    proof_keywords = [
        "transaction", "utr", "receipt", "reference", 
        "payment id", "txn", "transaction id", "ref number",
        "reference number", "paid on", "transaction number"
    ]
    
    # If ANY proof keyword is present, classify as HAS_PROOF
    if any(keyword in user_lower for keyword in proof_keywords):
        print(f"[VERIFICATION] Rule-based: HAS_PROOF detected - '{user_message[:50]}'")
        return {"verification_result": "HAS_PROOF"}

    # Otherwise, fall through to LLM classification
    try:
        client = get_azure_client()
    except Exception:
        return {"verification_result": "UNCLEAR"}

    system_prompt = """You are a debt collection verification decision engine.
The customer has already been asked to provide payment proof.
Classify their response strictly.
RESULT TYPES:
- HAS_PROOF → Customer mentions ANY of: transaction ID, transaction number, UTR, receipt number, reference number, payment ID, transaction reference, OR provides date + amount
- NO_PROOF → Clearly says they don't have proof OR refuses to provide
- UNAUTHORIZED → Paid a person/agent instead of official channel
- UNCLEAR → None of the above
EXAMPLES OF HAS_PROOF:
- "transaction id #7654"
- "my transaction id is ABC123"
- "I paid on 15th Jan, 250000"
- "UTR number 123456789"
- "receipt number XYZ"
- "reference number 7654"
- "transaction Id #7654, 15th jan, 250,000"
EXAMPLES OF NO_PROOF:
- "I don't have the receipt"
- "I lost the transaction details"
- "I can't find it"
Be LENIENT for HAS_PROOF - if customer provides ANY payment identifier or date+amount, classify as HAS_PROOF.

Return ONLY valid JSON.

FORMAT:
{
  "verification_result": "<RESULT>"
}
"""

    user_prompt = f"""
Customer response:
"{user_message}"
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=50,
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        return {
            "verification_result": parsed.get("verification_result", "UNCLEAR")
        }

    except Exception:
        return {"verification_result": "UNCLEAR"}