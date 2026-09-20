"""
ai/jev.py
---------
Thin wrapper around the OpenRouter Decisions API for the Jev model.

Endpoint : POST https://openrouter.ai/api/alpha/decisions
Model    : typesafe/jev-1.13
Auth     : Bearer $OPENROUTER_API_KEY

Jev is a System One model — it does not generate text.
It accepts a *state* (any JSON) and a map of typed *questions*, each of type
"choice", and returns calibrated answers.

For Mario we ask four choice questions per decision:
    move     — LEFT / RIGHT / NEUTRAL
    jump     — yes / no
    boost    — yes / no
    duration — 4 / 6 / 8 / 12 / 20  (frames to hold this action)
"""

from __future__ import annotations

import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

DECISIONS_URL   = "https://openrouter.ai/api/alpha/decisions"
MODEL           = os.getenv("JEV_MODEL", "typesafe/jev-1.13")
REQUEST_TIMEOUT = int(os.getenv("JEV_TIMEOUT", "10"))

# ---------------------------------------------------------------------------
# Criteria dicts — all questions must be "choice" type on the Jev API
# ---------------------------------------------------------------------------

MOVE_CRITERIA = {
    "LEFT":    "Move Mario left (hold left key)",
    "RIGHT":   "Move Mario right (hold right key) — default forward direction",
    "NEUTRAL": "No horizontal input — let Mario slow to a stop",
}

JUMP_CRITERIA = {
    "yes": "Press jump — launch Mario upward",
    "no":  "Do not jump",
}

BOOST_CRITERIA = {
    "yes": "Hold run/boost — Mario accelerates to max speed",
    "no":  "Normal speed",
}

DURATION_CRITERIA = {
    "4":  "4 frames — very reactive, reassess almost immediately",
    "6":  "6 frames — short, for near-instant threats",
    "8":  "8 frames — normal reaction time",
    "12": "12 frames — commit for a beat (path is clear nearby)",
    "20": "20 frames — commit long (nothing blocking for many tiles)",
}

# ---------------------------------------------------------------------------
# State builder
# ---------------------------------------------------------------------------

def _build_state(observation: dict) -> dict:
    """
    Enrich the raw observation with a plain-English summary so Jev has a
    strong natural-language anchor. Include explicit spatial warnings.
    """
    p        = observation.get("player", {})
    nearby   = observation.get("nearby", {})
    enemies  = nearby.get("enemies", [])
    obs      = observation.get("obstacles", {})
    level    = observation.get("level", {})

    # --- Enemy summary ---
    enemy_txt = "none nearby"
    if enemies:
        e = enemies[0]
        direction = "AHEAD" if e["relative_x"] > 0 else "BEHIND"
        dist_tiles = abs(e["relative_x"]) // 32
        enemy_txt = (
            f"{e.get('enemy_type','enemy')} is {dist_tiles} tiles {direction} "
            f"(vx={e.get('vx',0):.1f})"
        )

    # --- Obstacle summary ---
    wall_txt = "none"
    if obs.get("wall_ahead"):
        dist_px = obs.get("wall_dist_px", "?")
        h       = obs.get("wall_height", 1)
        dist_t  = (dist_px // 32) if dist_px else "?"
        wall_txt = (
            f"WALL {dist_t} tiles ahead ({dist_px}px), height={h} tiles — "
            f"MUST jump to get over it"
        )

    gap_txt = "NONE" if not obs.get("gap_ahead") else "GAP AHEAD — jump to cross or wait"

    # --- Velocity summary ---
    vx, vy = p.get("vx", 0), p.get("vy", 0)
    moving_txt = (
        f"moving right at {vx:.1f}px/f" if vx > 0.5 else
        f"moving left at {abs(vx):.1f}px/f" if vx < -0.5 else
        "nearly stopped (vx≈0)"
    )

    summary = (
        f"Mario world-x={p.get('x',0)}px (tile {p.get('tile_x',0)}), "
        f"y={p.get('y',0)}px, {moving_txt}. "
        f"On ground: {p.get('on_ground', False)}. "
        f"In air: {p.get('in_air', False)} (vy={vy:.1f}). "
        f"Power: {p.get('power','small')}. "
        f"Nearest enemy: {enemy_txt}. "
        f"Wall ahead: {wall_txt}. "
        f"Gap ahead: {gap_txt}. "
        f"Remaining level distance: {level.get('remaining_distance','?')}px."
    )

    return {
        **observation,
        "summary": summary,
        "goal": (
            "You are the AI controlling Mario in a side-scrolling platform game. "
            "The level scrolls to the RIGHT. Your mission:\n"
            "1. ALWAYS keep moving RIGHT — forward progress is the primary goal.\n"
            "2. When a WALL is detected ahead (pipe, block, ledge), you MUST JUMP "
            "   before reaching it. Jump when wall_dist_px < 96 (3 tiles).\n"
            "3. Jump ON TOP of enemies (Goombas, Koopas) to defeat them — "
            "   time the jump so Mario lands on them from above.\n"
            "4. If an enemy is fewer than 3 tiles ahead and at the same height, JUMP NOW.\n"
            "5. Use BOOST whenever the path ahead is clear of walls and enemies.\n"
            "6. NEVER stop moving right unless an enemy is directly in front "
            "   and cannot be jumped over."
        ),
    }

# ---------------------------------------------------------------------------
# Main API call
# ---------------------------------------------------------------------------

def ask_jev(observation: dict) -> dict:
    """
    Ask Jev what Mario should do next.

    Returns:
        {
            "move":            "LEFT" | "RIGHT" | "NEUTRAL",
            "jump":            bool,
            "boost":           bool,
            "duration_frames": int,
            "latency_ms":      float,
        }

    Raises:
        RuntimeError: on missing API key or non-2xx response.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file."
        )

    state = _build_state(observation)

    # Build jump instructions dynamically based on current state
    obs = observation.get("obstacles", {})
    wall_dist = obs.get("wall_dist_px") or 9999
    enemies   = observation.get("nearby", {}).get("enemies", [])
    nearest_enemy_dist = min(
        (e["relative_x"] for e in enemies if e.get("alive") and e.get("relative_x", 999) > 0),
        default=9999
    )
    player = observation.get("player", {})

    jump_hint = "Do not jump unless necessary."
    if obs.get("wall_ahead") and wall_dist < 96:
        jump_hint = f"WALL {wall_dist}px ahead — JUMP NOW to clear it."
    elif nearest_enemy_dist < 96:
        jump_hint = f"ENEMY {nearest_enemy_dist}px ahead — JUMP to stomp it."
    elif obs.get("gap_ahead"):
        jump_hint = "GAP ahead — JUMP to cross it."
    elif player.get("in_air"):
        jump_hint = "Mario is already in the air — do NOT jump (already jumping)."

    payload = {
        "model": MODEL,
        "state": state,
        "questions": {
            "move": {
                "type": "choice",
                "instructions": (
                    "Which horizontal direction should Mario move? "
                    "Default is RIGHT (forward). Only pick LEFT if critically necessary. "
                    "NEVER pick NEUTRAL when there is a clear path ahead."
                ),
                "criteria": MOVE_CRITERIA,
            },
            "jump": {
                "type": "choice",
                "instructions": (
                    f"Should Mario jump? "
                    f"{jump_hint} "
                    f"Jump only if: (a) a wall/pipe is within 3 tiles ahead, "
                    f"(b) an enemy is within 3 tiles at same height, or "
                    f"(c) a gap must be crossed. "
                    f"Do NOT jump randomly while moving through clear space."
                ),
                "criteria": JUMP_CRITERIA,
            },
            "boost": {
                "type": "choice",
                "instructions": (
                    "Should Mario run at full speed? "
                    "Use boost when no wall or enemy is within 5 tiles ahead. "
                    "Disable boost only if precise slow movement is needed."
                ),
                "criteria": BOOST_CRITERIA,
            },
            "duration": {
                "type": "choice",
                "instructions": (
                    "How many game frames should this action last? "
                    "Use 4-6 frames when an enemy or wall is very close (need quick re-decision). "
                    "Use 8-12 frames for normal forward movement. "
                    "Use 20 frames only on a completely open stretch."
                ),
                "criteria": DURATION_CRITERIA,
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "http://localhost:0",
        "X-OpenRouter-Title": "JevMario",
    }

    t0 = time.perf_counter()
    resp = requests.post(
        DECISIONS_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    if not resp.ok:
        raise RuntimeError(
            f"Jev API error {resp.status_code}: {resp.text}"
        )

    data    = resp.json()
    answers = data.get("answers", {})

    # --- move ---
    move = answers.get("move", {}).get("choice", "RIGHT")

    # --- jump ---
    jump = answers.get("jump", {}).get("choice", "no") == "yes"

    # --- boost ---
    boost = answers.get("boost", {}).get("choice", "no") == "yes"

    # --- duration ---
    dur_key = answers.get("duration", {}).get("choice", "8")
    try:
        duration_frames = int(dur_key)
    except (ValueError, TypeError):
        duration_frames = 8

    return {
        "move":            move,
        "jump":            jump,
        "boost":           boost,
        "duration_frames": duration_frames,
        "latency_ms":      round(latency_ms, 1),
    }
