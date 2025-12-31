# src/utils/llm.py

"""
LLM utilities.
Rule-based intent classification to keep the system fully self-contained.
External LLMs can be enabled later if required.
"""

from dotenv import load_dotenv
import os

load_dotenv()

USE_EXTERNAL_LLM = False  # Reserved for future Gemini/OpenAI integration


def classify_intent(prompt: str) -> str:
    """
    Classify customer payment intent based on rule-based matching.

    Possible intents:
    - paid
    - disputed
    - callback
    - unable
    - willing
    - unknown
    """

    text = prompt.lower()

    # 1. Already paid
    if any(x in text for x in [
        "already paid",
        "paid",
        "payment done"
    ]):
        return "paid"

    # 2. Dispute
    if any(x in text for x in [
        "wrong",
        "not my loan",
        "dispute",
        "incorrect",
        "never took"
    ]):
        return "disputed"

    # 3. Callback request (must be checked before payment intent)
    if any(x in text for x in [
        "call later",
        "call me later",
        "callback",
        "call me",
        "next week",
        "later"
    ]):
        return "callback"

    # 4. Unable to pay
    if any(x in text for x in [
        "can't pay",
        "cannot pay",
        "no money",
        "financial",
        "not able to pay"
    ]):
        return "unable"

    # 5. Willing to pay
    if any(x in text for x in [
        "pay",
        "payment",
        "settle",
        "installment",
        "emi"
    ]):
        return "willing"

    # 6. Fallback
    return "unknown"


def generate_response(prompt: str) -> str:
    """
    Generate short, neutral, voice-friendly responses.
    """

    return "Understood. Let me guide you through the next steps."
