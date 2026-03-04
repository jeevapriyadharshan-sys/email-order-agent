# backend/app/extraction/gemini_layer.py
from __future__ import annotations

from typing import Dict, Any
import json
import re

from .regex_layer import REQUIRED_FIELDS


def _strip_code_fences(s: str) -> str:
    """
    Gemini sometimes returns:
      ```json
      {...}
      ```
    This removes those fences safely.
    """
    s = (s or "").strip()
    # remove triple backtick blocks
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _safe_weight(v: Any):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        # extract first number from string like "55 kg"
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", v)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None


def extract_with_gemini(
    text: str,
    partial: Dict[str, Any],
    api_key: str,
    model_name: str,
) -> Dict[str, Any]:
    """
    Gemini extraction layer (AI fallback).
    Returns a dict ONLY (no tuple).

    If api_key is empty, returns partial unchanged.
    """
    partial = partial or {}
    if not api_key:
        return dict(partial)

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt = f"""
Extract logistics order details from the email into JSON with keys:
customer_name, weight_kg, pickup_location, drop_location, pickup_time_window.
If unknown, set as empty string. Return ONLY JSON (no markdown).

EMAIL:
{text}

PARTIAL (regex extracted):
{partial}
""".strip()

    resp = model.generate_content(prompt)
    raw = getattr(resp, "text", "") or ""
    cleaned = _strip_code_fences(raw)

    ai_fields = json.loads(cleaned)
    if not isinstance(ai_fields, dict):
        raise ValueError("Gemini output is not a JSON object")

    merged = dict(partial)

    # Fill only missing/empty fields conservatively
    for k, v in ai_fields.items():
        if k not in REQUIRED_FIELDS:
            continue
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if k not in merged or merged.get(k) in (None, ""):
            merged[k] = v

    # Normalize weight
    if "weight_kg" in merged:
        w = _safe_weight(merged["weight_kg"])
        if w is not None:
            # Keep as int if close to int, else float
            merged["weight_kg"] = int(w) if abs(w - int(w)) < 1e-9 else w

    return merged