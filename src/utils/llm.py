# src/utils/llm.py

"""
LLM utilities.
Falls back to rule-based logic if external LLM is unavailable.
"""

from dotenv import load_dotenv
import os

load_dotenv()

USE_EXTERNAL_LLM = False  # Toggle if Gemini/OpenAI becomes available


def classify_intent(prompt: str) -> str:
    """
    Classify payment intent.
    Rule-based fallback to keep system self-contained.
    """

    text = prompt.lower()

    if any(x in text for x in ["already paid", "paid", "payment done"]):
        return "paid"

    if any(x in text for x in ["wrong", "not my loan", "dispute", "incorrect"]):
        return "disputed"

    if any(x in text for x in ["can't pay", "cannot pay", "no money", "financial"]):
        return "unable"

    if any(x in text for x in ["pay", "payment", "settle", "installment"]):
        return "willing"

    if any(x in text for x in ["call later", "callback", "later"]):
        return "callback"

    return "unknown"


def generate_response(prompt: str) -> str:
    """
    Generate short, professional responses.
    """

    # Keep voice-friendly and neutral
    return "Understood. Let me guide you through the next steps."
