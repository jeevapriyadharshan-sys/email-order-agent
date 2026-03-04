# backend/app/extraction/regex_layer.py
import re
from typing import Dict, Any, Optional

# Used by worker/review/gemini for consistent completeness checks
REQUIRED_FIELDS = [
    "customer_name",
    "weight_kg",
    "pickup_location",
    "drop_location",
    "pickup_time_window",
]


def _find(text: str, patterns) -> Optional[str]:
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return (m.group(1) or "").strip()
    return None


def extract_with_regex(text: str) -> Dict[str, Any]:
    """
    Regex extraction layer (deterministic).
    MUST return a dict only.

    Keys (when found):
      customer_name, weight_kg, pickup_location, drop_location, pickup_time_window
    """
    out: Dict[str, Any] = {}

    # Name
    name = _find(text, [
        r"Customer\s*Name:\s*(.+)",
        r"Name:\s*(.+)",
        r"Customer:\s*(.+)",
    ])
    if name:
        out["customer_name"] = name

    # Weight: strict capture to avoid mapping "one truck" to weight
    weight = _find(text, [
        r"Weight:\s*([0-9]+(?:\.[0-9]+)?)\s*kg\b",
        r"Weight\s*of\s*goods:\s*([0-9]+(?:\.[0-9]+)?)\s*kg\b",
        r"Weight\s*of\s*goods:\s*([0-9]+(?:\.[0-9]+)?)\b",
    ])
    if weight:
        try:
            out["weight_kg"] = int(float(weight))
        except Exception:
            # keep raw if weird format
            out["weight_kg"] = weight

    # Pickup / Drop
    pickup = _find(text, [
        r"Pickup\s*Location:\s*(.+)",
        r"Pickup:\s*(.+)",
        r"From:\s*(.+)",
    ])
    if pickup:
        out["pickup_location"] = pickup

    drop = _find(text, [
        r"Drop\s*Location:\s*(.+)",
        r"Drop\s*off:\s*(.+)",
        r"To:\s*(.+)",
    ])
    if drop:
        out["drop_location"] = drop

    # Time window
    pickup_date = _find(text, [
        r"Pickup\s*Date:\s*(.+)",
        r"Pickup\s*scheduled\s*for:\s*(.+)",
        r"Pickup\s+on\s+(.+)",
    ])
    delivery_deadline = _find(text, [
        r"Delivery\s*Deadline:\s*(.+)",
        r"Delivery\s*by:\s*(.+)",
        r"Deliver\s+by\s+(.+)",
    ])

    if pickup_date and delivery_deadline:
        out["pickup_time_window"] = f"{pickup_date} → {delivery_deadline}"
    else:
        # fallback: any explicit time window line
        tw = _find(text, [
            r"Pickup\s*Time\s*Window:\s*(.+)",
            r"Time\s*Window:\s*(.+)",
        ])
        if tw:
            out["pickup_time_window"] = tw

    return out