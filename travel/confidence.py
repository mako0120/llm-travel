"""Deterministic uncertainty labels and fallbacks for retrieved travel facts."""

CONFIDENCE_LEVELS = ("high", "medium", "low", "unknown")
FALLBACKS = ("continue_with_labels", "ask_user", "exclude_candidate", "stop")


def fallback_for(confidence, *, required=False, budget_sensitive=False, alternative_available=False):
    """Choose a conservative fallback without treating an uncertain fact as true."""
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError("confidence is invalid")
    if not all(type(value) is bool for value in (required, budget_sensitive, alternative_available)):
        raise ValueError("fallback context flags must be boolean")
    if confidence in ("high", "medium"):
        return "continue_with_labels"
    if required:
        return "stop"
    if budget_sensitive:
        return "ask_user"
    if alternative_available:
        return "exclude_candidate"
    return "continue_with_labels"


def display_label(confidence):
    """Return traveler-facing text; no label implies verified-but-still-sourced context."""
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError("confidence is invalid")
    return {"high": "出典確認済み", "medium": "出典を確認中", "low": "情報未確定", "unknown": "未確認"}[confidence]


def cost_presentation(items):
    """Label totals as estimates whenever a supplied cost item is uncertain."""
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a nonempty list")
    if any(not isinstance(item, dict) or item.get("confidence") not in CONFIDENCE_LEVELS for item in items):
        raise ValueError("each item must include valid confidence")
    return "概算" if any(item["confidence"] in ("low", "unknown") for item in items) else "合計"
