# backend/app/extraction/gemini_layer.py
from __future__ import annotations

from typing import Dict, Any
import json
import re

from .regex_layer import REQUIRED_FIELDS


def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _safe_weight(v: Any):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        # Reject 0 or suspiciously low values
        if float(v) <= 0:
            return None
        return v
    if isinstance(v, str):
        v = v.strip()
        if not v or v.lower() in ("unknown", "n/a", "null", "none", "not mentioned", "not provided", ""):
            return None
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", v)
        if not m:
            return None
        try:
            val = float(m.group(1))
            if val <= 0:
                return None
            return val
        except Exception:
            return None
    return None


def _is_hallucinated(field: str, value: Any) -> bool:
    """
    Detect common Gemini hallucination patterns.
    Returns True if the value should be rejected.
    """
    if value is None:
        return True
    s = str(value).strip().lower()
    # Reject placeholder/unknown values
    if s in ("", "unknown", "n/a", "null", "none", "not mentioned",
             "not provided", "not specified", "not available",
             "to be confirmed", "tbd", "na", "-", "?"):
        return True
    # Reject if it looks like a template placeholder
    if re.search(r"\[.*?\]|\{.*?\}", s):
        return True
    return False


def extract_with_gemini(
    text: str,
    partial: Dict[str, Any],
    api_key: str,
    model_name: str,
) -> Dict[str, Any]:
    """
    Gemini extraction layer (AI fallback).
    Returns a dict ONLY (no tuple).
    Only fills fields that are EXPLICITLY present in the email.
    """
    partial = partial or {}
    if not api_key:
        return dict(partial)

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    # Identify which fields are still missing
    missing = [
        k for k in REQUIRED_FIELDS
        if k not in partial or partial.get(k) in (None, "")
    ]

    prompt = f"""
You are a strict data extractor for logistics transport requests.

Extract ONLY the following fields from the email below:
{json.dumps(missing)}

CRITICAL RULES:
1. Only extract values that are EXPLICITLY written in the email.
2. Do NOT guess, infer, or assume any value.
3. Do NOT use placeholder text like "unknown" or "N/A".
4. If a field is not mentioned in the email, set it to null.
5. For weight_kg: only extract if an explicit number with weight unit (kg, tons, etc.) is present. Return null if no weight is mentioned.
6. Return ONLY a valid JSON object. No markdown, no explanation.

EMAIL:
{text}

Already extracted (do not change these):
{json.dumps(partial)}

Return JSON with only these keys: {json.dumps(missing)}
""".strip()

    try:
        resp = model.generate_content(prompt)
        raw = getattr(resp, "text", "") or ""
        cleaned = _strip_code_fences(raw)
        ai_fields = json.loads(cleaned)
        if not isinstance(ai_fields, dict):
            raise ValueError("Gemini output is not a JSON object")
    except Exception:
        # If Gemini fails, return partial unchanged
        return dict(partial)

    merged = dict(partial)

    # Fill only missing fields, with strict hallucination check
    for k in missing:
        if k not in ai_fields:
            continue
        v = ai_fields[k]

        # Reject hallucinated values
        if _is_hallucinated(k, v):
            continue

        # Special handling for weight
        if k == "weight_kg":
            w = _safe_weight(v)
            if w is not None:
                merged[k] = int(w) if abs(w - int(w)) < 1e-9 else w
            # If weight not valid, do NOT set it — leave it missing
            continue

        # For other fields, only accept non-empty strings
        if isinstance(v, str) and v.strip():
            merged[k] = v.strip()
        elif v is not None and not isinstance(v, str):
            merged[k] = v

    return merged