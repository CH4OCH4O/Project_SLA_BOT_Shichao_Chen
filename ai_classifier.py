from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from classifier import classify_message
from utils import message_excerpt


logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)
VALID_SENTIMENTS = {"positive", "neutral", "negative"}
VALID_PRIORITIES = {"low", "medium", "high"}
CHANNEL_MATCH_CONFIDENCE_THRESHOLD = 0.75


def _rule_based_customer_classification(text: str, reason_prefix: str | None = None) -> dict[str, Any]:
    result = classify_message(text)
    priority_map = {
        "urgent": "high",
        "high": "high",
        "normal": "medium",
        "medium": "medium",
        "low": "low",
    }
    normalized = (text or "").lower()
    if any(term in normalized for term in ("urgent", "blocked", "cannot", "can't", "failed", "error")):
        sentiment = "negative"
    elif any(term in normalized for term in ("thanks", "thank you", "solved", "figured it out", "no worries")):
        sentiment = "positive"
    else:
        sentiment = "neutral"

    reason = result.get("reason", "Rule-based fallback classification.")
    if reason_prefix:
        reason = f"{reason_prefix} {reason}"

    return {
        "needs_response": bool(result.get("requires_response")),
        "sentiment": sentiment,
        "priority": priority_map.get(result.get("priority"), "medium"),
        "reason": reason,
        "classifier_source": "rule_based",
    }


def _gemini_key() -> str | None:
    return os.getenv("GEMINI_API_KEY")


def _extract_json_object(text: str) -> dict[str, Any]:
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini response was not a JSON object.")
    return parsed


def _call_gemini(prompt: str) -> dict[str, Any]:
    key = _gemini_key()
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{GEMINI_ENDPOINT}?key={key}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    body = json.loads(raw)
    text = (
        body.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    if not text:
        raise ValueError("Gemini returned an empty response.")
    return _extract_json_object(text)


def _gemini_json_with_retry(prompt: str) -> dict[str, Any]:
    if not _gemini_key():
        logger.warning("GEMINI_API_KEY is missing; falling back to rule-based classifier.")
        raise RuntimeError("Missing GEMINI_API_KEY")

    last_error: Exception | None = None
    for _ in range(2):
        try:
            return _call_gemini(prompt)
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini classification attempt failed: %s", exc)
    raise RuntimeError(f"Gemini failed after retry: {last_error}")


def classify_customer_message(text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """AI agent layer for customer message triage, with safe rule-based fallback."""
    prompt = f"""
You are classifying top-level customer Slack messages for a demo SLA reminder bot.
Return JSON only. Do not include markdown, comments, or extra text.

Decide whether the customer message requires an employee response.
Allowed values:
- needs_response: true or false
- sentiment: "positive", "neutral", or "negative"
- priority: "low", "medium", or "high"
- reason: short plain-English explanation

Messages like "I don't need help", "No worries, we figured it out", and "Thanks, that solved it" do not need a response.
Customer message: {json.dumps(text)}
Context: {json.dumps(context or {})}
""".strip()

    try:
        result = _gemini_json_with_retry(prompt)
        normalized = {
            "needs_response": bool(result.get("needs_response")),
            "sentiment": str(result.get("sentiment", "neutral")).lower(),
            "priority": str(result.get("priority", "medium")).lower(),
            "reason": str(result.get("reason", "Gemini classification."))[:500],
            "classifier_source": "gemini",
        }
        if normalized["sentiment"] not in VALID_SENTIMENTS:
            normalized["sentiment"] = "neutral"
        if normalized["priority"] not in VALID_PRIORITIES:
            normalized["priority"] = "medium"
        logger.info("Customer classification result: %s", normalized)
        return normalized
    except Exception as exc:
        fallback = _rule_based_customer_classification(text, f"Gemini fallback: {exc}.")
        logger.info("Customer classification result: %s", fallback)
        return fallback


def match_employee_response_to_case(
    employee_text: str,
    open_cases: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """AI agent layer for matching top-level employee messages to recent open cases."""
    if not open_cases:
        return {
            "is_response": False,
            "matched_case_id": None,
            "confidence": 0.0,
            "reason": "No recent open cases in this channel.",
            "classifier_source": "none",
        }

    case_payload = [
        {
            "case_id": case["case_id"],
            "customer_message": message_excerpt(case.get("message_text") or "", 240),
            "created_at": case.get("created_at"),
        }
        for case in open_cases
    ]
    allowed_ids = {case["case_id"] for case in open_cases}
    prompt = f"""
You are matching an employee's top-level Slack channel message to recent open customer SLA cases.
Return JSON only. Do not include markdown, comments, or extra text.

Determine whether the employee message is a valid response to one of the provided cases.
Only match if the employee message likely addresses the customer's issue. Do not match unrelated status messages.
Prefer the most recent relevant case if several are similar.
For vague messages such as "ok" or "checking", only match when one very recent case is clearly implied.

Allowed output:
- is_response: true or false
- matched_case_id: one of the provided case IDs, or null
- confidence: number between 0 and 1
- reason: short plain-English explanation

Employee message: {json.dumps(employee_text)}
Open cases: {json.dumps(case_payload)}
Context: {json.dumps(context or {})}
""".strip()

    try:
        result = _gemini_json_with_retry(prompt)
        matched_case_id = result.get("matched_case_id")
        confidence = float(result.get("confidence", 0) or 0)
        normalized = {
            "is_response": bool(result.get("is_response"))
            and matched_case_id in allowed_ids
            and confidence >= CHANNEL_MATCH_CONFIDENCE_THRESHOLD,
            "matched_case_id": matched_case_id if matched_case_id in allowed_ids else None,
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": str(result.get("reason", "Gemini channel match."))[:500],
            "classifier_source": "gemini",
        }
        if normalized["confidence"] < CHANNEL_MATCH_CONFIDENCE_THRESHOLD:
            normalized["is_response"] = False
        logger.info("Employee response matching result: %s", normalized)
        return normalized
    except Exception as exc:
        logger.info("Employee response matching result: Gemini unavailable/failed: %s", exc)
        return {
            "is_response": False,
            "matched_case_id": None,
            "confidence": 0.0,
            "reason": f"Gemini unavailable; no channel-level auto-match. {exc}",
            "classifier_source": "rule_based",
        }
