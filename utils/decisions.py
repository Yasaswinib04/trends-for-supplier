"""
Decision persistence — logs buyer Approve/Override actions.

MVP implementation uses a local JSON file (data/overrides.json).
Each entry follows the Override Database Schema from the PRD:
  - timestamp
  - trend_id
  - system_recommendation
  - buyer_action: "approve" | "override"
  - buyer_override_reason: Enum from the UI modal (or null for approve)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DECISIONS_FILE = DATA_DIR / "overrides.json"

# The 4 predefined override reasons (no free text)
OVERRIDE_REASONS = [
    "Supplier lead times",
    "Too premium for our base",
    "Costing/Margin break",
    "Internal design direction",
]


def _load_decisions():
    if DECISIONS_FILE.exists():
        try:
            with open(DECISIONS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_decisions(decisions):
    with open(DECISIONS_FILE, "w") as f:
        json.dump(decisions, f, indent=2, default=str)


def log_decision(trend_id, action, system_recommendation, override_reason=None):
    """
    Append a decision to the override log.

    Args:
        trend_id: The trend being decided on
        action: "approve" or "override"
        system_recommendation: The system's original suggestion string
        override_reason: One of OVERRIDE_REASONS (required if action == "override")
    """
    decisions = _load_decisions()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trend_id": trend_id,
        "system_recommendation": system_recommendation,
        "buyer_action": action,
        "buyer_override_reason": override_reason if action == "override" else None,
    }
    decisions.append(entry)
    _save_decisions(decisions)
    return entry


def get_decision(trend_id):
    """Get the most recent decision for a trend, or None."""
    decisions = _load_decisions()
    for d in reversed(decisions):
        if d["trend_id"] == trend_id:
            return d
    return None


def get_all_decisions():
    """Return all logged decisions."""
    return _load_decisions()


def clear_decision(trend_id):
    """Remove all decisions for a trend (for re-evaluation)."""
    decisions = _load_decisions()
    decisions = [d for d in decisions if d["trend_id"] != trend_id]
    _save_decisions(decisions)
