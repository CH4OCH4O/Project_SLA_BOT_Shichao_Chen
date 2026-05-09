from __future__ import annotations

import re


ACKNOWLEDGEMENTS = {
    "thanks",
    "thank you",
    "got it",
    "sounds good",
    "ok",
    "okay",
    "great",
    "nice",
    "perfect",
}

NO_RESPONSE_PHRASES = [
    "don't need help",
    "do not need help",
    "dont need help",
    "no help needed",
    "no worries",
    "figured it out",
    "we figured it out",
    "solved it",
    "that solved it",
]

RESPONSE_SIGNALS = [
    "help",
    "issue",
    "problem",
    "error",
    "bug",
    "not working",
    "failed",
    "cannot",
    "can't",
    "blocked",
    "urgent",
    "asap",
    "any update",
    "following up",
    "can you",
    "could you",
    "please check",
]

URGENT_SIGNALS = [
    "urgent",
    "asap",
    "blocked",
    "cannot continue",
    "production down",
    "can't continue",
]

HIGH_SIGNALS = ["any update", "following up"]
NORMAL_SIGNALS = ["issue", "error", "bug", "failed", "not working", "problem"]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _emoji_only(text: str) -> bool:
    cleaned = re.sub(r"[:_\-\+\d\s]", "", text or "")
    return bool(text.strip()) and not any(char.isalnum() for char in cleaned)


def classify_message(text: str) -> dict:
    normalized = _normalize(text)
    if not normalized:
        return {
            "requires_response": False,
            "category": "empty",
            "priority": "low",
            "reason": "Message is empty.",
        }

    if normalized in ACKNOWLEDGEMENTS:
        return {
            "requires_response": False,
            "category": "acknowledgement",
            "priority": "low",
            "reason": "Short acknowledgement.",
        }

    if any(phrase in normalized for phrase in NO_RESPONSE_PHRASES):
        return {
            "requires_response": False,
            "category": "no_help_needed",
            "priority": "low",
            "reason": "Customer says no employee help is needed.",
        }

    if _emoji_only(normalized):
        return {
            "requires_response": False,
            "category": "emoji_only",
            "priority": "low",
            "reason": "Emoji-only message.",
        }

    matched = [signal for signal in RESPONSE_SIGNALS if signal in normalized]
    has_question = "?" in normalized
    requires_response = bool(matched or has_question)

    if not requires_response:
        return {
            "requires_response": False,
            "category": "general",
            "priority": "low",
            "reason": "No response-required signal matched.",
        }

    priority = "normal"
    if any(signal in normalized for signal in URGENT_SIGNALS):
        priority = "urgent"
    elif any(signal in normalized for signal in HIGH_SIGNALS):
        priority = "high"
    elif any(signal in normalized for signal in NORMAL_SIGNALS):
        priority = "normal"

    reasons = []
    if matched:
        reasons.append(f"Matched signals: {', '.join(matched)}.")
    if has_question:
        reasons.append("Contains a question mark.")

    return {
        "requires_response": True,
        "category": "support_request",
        "priority": priority,
        "reason": " ".join(reasons),
    }
