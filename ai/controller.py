"""
ai/controller.py
----------------
Main AI controller — owns the observe → decide → execute loop.

The controller is called from the game's main loop:

    ai = AIController(mario)
    ai.start()

    while game_running:
        ai.tick(frame_count)    # every frame; handles its own timing
        mario.update()          # game physics runs at full 60 FPS
        ...

    ai.stop()

Jev API calls are made in a background thread so the game never stalls.
"""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING

from ai.config import AI_CONFIG
from ai.observation import InternalStateProvider
from ai.executor import ActionExecutor
from ai.actions import validate_action, _fallback
from ai.logger import AILogger

if TYPE_CHECKING:
    from entities.Mario import Mario


class AIController:
    """
    Wraps observation + decision + execution.

    Args:
        mario:          The Mario entity.
        decision_model: A DecisionModel instance.
    """

    def __init__(self, mario: "Mario", decision_model):
        self._mario  = mario
        self._model  = decision_model

        self._obs_provider = InternalStateProvider(mario)
        self._executor     = ActionExecutor(mario)
        self._logger       = AILogger()

        cfg = AI_CONFIG
        self._debug = cfg["debug_ai_state"]

        # Thread state
        self._lock               = threading.Lock()
        self._pending_action: dict | None = None
        self._decision_in_flight = False

        # Session counters
        self._frame = 0
        self._life  = 0

        # Exposed for debug overlay
        self._last_action: dict      = _fallback()
        self._last_latency_ms: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        print("[AI] Controller started", file=sys.stderr)

    def stop(self) -> None:
        summary = self._logger.summary()
        print(f"[AI] Session summary: {summary}", file=sys.stderr)
        self._logger.close()

    # ------------------------------------------------------------------
    # Main tick — call every game frame, BEFORE mario.update()
    # ------------------------------------------------------------------

    def tick(self, frame: int | None = None) -> None:
        """
        1. Latch any completed async decision into the executor.
        2. Apply the current action to Mario's traits for this frame.
        3. If the action is near expiration and no request is in-flight, launch one.
        """
        if frame is not None:
            self._frame = frame

        # Latch finished async decision
        with self._lock:
            if self._pending_action is not None:
                self._executor.apply(self._pending_action)
                self._pending_action     = None
                self._decision_in_flight = False

        # Drive Mario for this frame
        self._executor.tick()

        # Fire async decision when action is near expiration (or expired) and thread is free
        if not self._decision_in_flight and (self._executor.ready_for_new_action or self._executor._frames_remaining <= 4):
            self._fire_async_decision()

    # ------------------------------------------------------------------
    # Death / restart
    # ------------------------------------------------------------------

    def on_mario_death(self) -> None:
        self._logger.log_death(
            frame   = self._frame,
            mario_x = self._mario.rect.x,
            life    = self._life,
        )
        self._life += 1
        self._executor.reset()
        self._decision_in_flight = False
        with self._lock:
            self._pending_action = None

    # ------------------------------------------------------------------
    # Debug info for overlay
    # ------------------------------------------------------------------

    @property
    def debug_info(self) -> dict:
        return {
            "frame":       self._frame,
            "life":        self._life,
            "action":      self._last_action,
            "frames_left": self._executor._frames_remaining,
            "latency_ms":  self._last_latency_ms,
            "decisions":   self._logger.decisions,
            "deaths":      self._logger.deaths,
            "in_flight":   self._decision_in_flight,
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _fire_async_decision(self) -> None:
        """Snapshot observation now (main thread) then run model in background."""
        self._decision_in_flight = True
        observation = self._obs_provider.get_state()

        t = threading.Thread(
            target = self._decide_thread,
            args   = (observation,),
            daemon = True,
        )
        t.start()

    def _decide_thread(self, observation: dict) -> None:
        """Runs in a background thread; writes result through the lock."""
        try:
            raw    = self._model.decide(observation)
            action = validate_action(raw, max_duration=AI_CONFIG["max_action_duration_frames"])
        except Exception as exc:
            print(f"[AI] Decision error: {exc}", file=sys.stderr)
            action = _fallback()
            raw    = {}

        latency = raw.get("latency_ms", 0.0) if isinstance(raw, dict) else 0.0
        self._last_latency_ms = latency
        self._last_action     = action

        self._logger.log_decision(
            frame        = self._frame,
            observation  = observation,
            raw_response = raw,
            action       = action,
            latency_ms   = latency,
            mario_x      = self._mario.rect.x,
            life         = self._life,
        )

        with self._lock:
            self._pending_action = action
