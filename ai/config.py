"""
ai/config.py
------------
All tuneable Jev-AI parameters in one place.
Values are read from environment variables (with sane defaults) so nothing
needs to be hard-coded.

Usage:
    from ai.config import AI_CONFIG
    interval = AI_CONFIG["decision_interval_frames"]
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _bool(key: str, default: bool) -> bool:
    val = os.getenv(key, str(default)).strip().lower()
    return val not in ("0", "false", "no", "off")


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


AI_CONFIG = {
    # --- Timing ---
    # How many game frames between consecutive Jev decisions.
    # Jev will be queried asynchronously, so the game keeps running.
    "decision_interval_frames": _int("AI_DECISION_INTERVAL_FRAMES", 6),

    # Hard ceiling on how many frames a single action can last.
    "max_action_duration_frames": _int("MAX_ACTION_DURATION_FRAMES", 30),

    # --- Mode ---
    # "jev"        : use the real Jev API
    # "rule"       : use the built-in right-walking rule model (no API needed)
    "ai_mode": os.getenv("AI_MODE", "jev").strip().lower(),

    # --- Debug overlay ---
    "debug_ai_state": _bool("DEBUG_AI_STATE", True),

    # --- Logging ---
    "log_decisions": _bool("LOG_AI_DECISIONS", True),
}
