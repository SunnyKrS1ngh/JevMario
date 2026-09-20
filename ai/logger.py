"""
ai/logger.py
------------
Lightweight session logger for the Jev Mario controller.

Writes one JSON-Lines file per session:
    logs/jev_mario_<timestamp>.jsonl

Each line is a JSON object:
    {
        "t":           <ISO timestamp>,
        "frame":       <game frame count>,
        "observation": {...},
        "raw_response": {...},
        "action":      {...},
        "latency_ms":  123.4,
        "mario_x":     200,
        "life":        0
    }
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone


class AILogger:
    """
    Optional session logger.  Disabled automatically if LOG_AI_DECISIONS is
    not set or is falsy.
    """

    def __init__(self, log_dir: str = "./logs"):
        self._enabled = os.getenv("LOG_AI_DECISIONS", "1").strip() not in ("0", "false", "False", "")
        self._file = None

        if self._enabled:
            os.makedirs(log_dir, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = os.path.join(log_dir, f"jev_mario_{ts}.jsonl")
            try:
                self._file = open(path, "w", encoding="utf-8")
                print(f"[AI] Logging to {path}", file=sys.stderr)
            except OSError as exc:
                print(f"[AI] Logger could not open file: {exc}", file=sys.stderr)
                self._enabled = False

        # Running totals
        self.deaths = 0
        self.decisions = 0
        self.invalid_responses = 0
        self.total_latency_ms = 0.0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def log_decision(
        self,
        *,
        frame: int,
        observation: dict,
        raw_response: dict,
        action: dict,
        latency_ms: float,
        mario_x: int,
        life: int,
    ) -> None:
        self.decisions += 1
        self.total_latency_ms += latency_ms

        if not self._enabled or self._file is None:
            return

        entry = {
            "t": datetime.now(timezone.utc).isoformat(),
            "frame": frame,
            "observation": observation,
            "raw_response": raw_response,
            "action": action,
            "latency_ms": latency_ms,
            "mario_x": mario_x,
            "life": life,
        }
        self._file.write(json.dumps(entry) + "\n")
        self._file.flush()

    def log_death(self, *, frame: int, mario_x: int, life: int) -> None:
        self.deaths += 1
        if not self._enabled or self._file is None:
            return
        entry = {
            "t": datetime.now(timezone.utc).isoformat(),
            "event": "death",
            "frame": frame,
            "mario_x": mario_x,
            "life": life,
        }
        self._file.write(json.dumps(entry) + "\n")
        self._file.flush()

    def summary(self) -> dict:
        avg_lat = (self.total_latency_ms / self.decisions) if self.decisions > 0 else 0
        return {
            "decisions": self.decisions,
            "deaths": self.deaths,
            "invalid_responses": self.invalid_responses,
            "avg_latency_ms": round(avg_lat, 1),
        }

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None
