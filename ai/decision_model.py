"""
ai/decision_model.py
--------------------
Thin abstraction separating game code from any specific AI backend.

The controller uses DecisionModel, never JevDecisionModel directly.
This allows swapping Jev for a rule-based or local model without touching
any game code.
"""

from __future__ import annotations

from ai.actions import validate_action, _fallback, NEUTRAL_ACTION


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class DecisionModel:
    """
    All models implement decide().
    Returns the raw response dict (including latency_ms etc.);
    the caller is responsible for validation via validate_action().
    """

    def decide(self, observation: dict) -> dict:
        """
        Given a game observation, return a raw action dict.

        The returned dict MUST be passable to validate_action().
        It MAY also include extra keys like "latency_ms" that the
        controller uses for logging.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Jev-backed implementation
# ---------------------------------------------------------------------------

class JevDecisionModel(DecisionModel):
    """Calls the Jev API and returns the raw response (latency_ms included)."""

    def __init__(self, max_duration: int = 30):
        from ai.jev import ask_jev
        self._ask_jev      = ask_jev
        self._max_duration = max_duration
        self._last_raw: dict = dict(NEUTRAL_ACTION)

    def decide(self, observation: dict) -> dict:
        try:
            raw = self._ask_jev(observation)
        except Exception as exc:
            import sys
            print(f"[AI] Jev call failed: {exc}", file=sys.stderr)
            # Return last valid raw with latency 0 so the loop doesn't crash
            return dict(self._last_raw)

        self._last_raw = raw
        return raw


# ---------------------------------------------------------------------------
# Rule-based fallback (no API key needed — for testing)
# ---------------------------------------------------------------------------

class RuleBasedModel(DecisionModel):
    """
    Deterministic rule-based controller:
      - Always move RIGHT with boost
      - Jump when a wall or enemy is close ahead
    """

    def decide(self, observation: dict) -> dict:
        player  = observation.get("player", {})
        nearby  = observation.get("nearby", {})
        enemies = nearby.get("enemies", [])
        obs     = observation.get("obstacles", {})

        move  = "RIGHT"
        boost = True
        jump  = False

        # Jump over walls/pipes
        wall_dist = obs.get("wall_dist_px") or 9999
        if obs.get("wall_ahead") and wall_dist < 96:
            jump = True

        # Jump over nearby enemies at same height
        if not jump:
            for e in enemies:
                rx = e.get("relative_x", 999)
                ry = e.get("relative_y", 999)
                if 0 < rx < 96 and abs(ry) < 32 and e.get("alive"):
                    jump = True
                    break

        # Jump over gaps
        if not jump and obs.get("gap_ahead"):
            jump = True

        # Don't jump if already in air
        if player.get("in_air"):
            jump = False

        duration = 6 if jump else (20 if not enemies and not obs.get("wall_ahead") else 8)

        return {
            "move":            move,
            "jump":            jump,
            "boost":           boost,
            "duration_frames": duration,
            "latency_ms":      0.0,
        }
