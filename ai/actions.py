"""
ai/actions.py
-------------
Action definitions and validation for the Jev Mario AI controller.

Jev outputs a structured action dict. This module:
  - Defines the valid action schema
  - Validates Jev's response
  - Returns a safe fallback on invalid output
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_MOVES = {"LEFT", "RIGHT", "NEUTRAL"}
MIN_DURATION = 1
MAX_DURATION = 60   # configurable ceiling; overridden by ai/config.py at runtime

# Action template
NEUTRAL_ACTION: dict = {"move": "NEUTRAL", "jump": False, "boost": False, "duration_frames": 6}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_action(raw: dict, max_duration: int = MAX_DURATION) -> dict:
    """
    Validate and normalise a raw action dict from Jev.

    Expected schema (all optional except 'move'):
        {
            "move":            "LEFT" | "RIGHT" | "NEUTRAL",
            "jump":            true | false,
            "boost":           true | false,
            "duration_frames": 1..max_duration
        }

    Returns a clean, valid action dict, or NEUTRAL on any problem.
    """
    if not isinstance(raw, dict):
        return _fallback("action is not a dict")

    move = raw.get("move", "NEUTRAL")
    if move not in VALID_MOVES:
        return _fallback(f"invalid move value: {move!r}")

    jump = bool(raw.get("jump", False))
    boost = bool(raw.get("boost", False))

    duration = raw.get("duration_frames", 6)
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        return _fallback(f"duration_frames not an integer: {duration!r}")

    duration = max(MIN_DURATION, min(duration, max_duration))

    return {
        "move": move,
        "jump": jump,
        "boost": boost,
        "duration_frames": duration,
    }


def _fallback(reason: str = "") -> dict:
    """Return a safe NEUTRAL action."""
    if reason:
        import sys
        print(f"[AI] Action fallback — {reason}", file=sys.stderr)
    return dict(NEUTRAL_ACTION)
