"""
ai/executor.py
--------------
Action Executor — translates a validated action dict into the game's
existing trait/control mechanism.

Key design principles for smooth platformer control:
1. Continuous momentum: Mario's primary goal is moving forward (RIGHT).
   When an action's duration expires while waiting for the next AI decision,
   Mario continues holding forward momentum rather than slamming to a dead halt.
2. Mid-air momentum: While Mario is in the air (jumping), directional input
   MUST be preserved so Mario does not lose horizontal velocity and drop straight down.
3. Jump triggering: JumpTrait.jump(True) only launches when onGround is True.
   We trigger it on ground contact and release it cleanly.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entities.Mario import Mario

MOVE_TO_DIRECTION = {
    "LEFT":    -1,
    "RIGHT":    1,
    "NEUTRAL":  0,
}


class ActionExecutor:
    """
    Applies an AI action to Mario for duration_frames consecutive frames.

    Usage (every game frame):
        executor.tick()   # call BEFORE mario.update()

    apply(action) — load a new action; tick() will hold it for duration_frames.
    """

    def __init__(self, mario: "Mario"):
        self._mario = mario
        self._current_action: dict | None = None
        self._frames_remaining: int = 0
        self._jump_triggered: bool = False
        self._last_direction: int = 1   # default forward direction is RIGHT
        self._last_boost: bool = True

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def ready_for_new_action(self) -> bool:
        """True when the current action has expired."""
        return self._frames_remaining <= 0

    def apply(self, action: dict) -> None:
        """Store a new action and reset the frame counter."""
        self._current_action   = action
        self._frames_remaining = action.get("duration_frames", 8)
        # Reset jump trigger so a new jump action can fire
        if action.get("jump"):
            self._jump_triggered = False

    def tick(self) -> None:
        """
        Called once per game frame (before mario.update()).
        Applies the active action or maintains momentum between decisions.
        """
        if self._current_action is not None and self._frames_remaining > 0:
            self._apply_action(self._current_action)
            self._frames_remaining -= 1
        else:
            # Action expired: maintain forward momentum while waiting for next decision
            self._apply_coasting()

    def reset(self) -> None:
        """Clear state on Mario death/restart."""
        self._current_action   = None
        self._frames_remaining = 0
        self._jump_triggered   = False
        self._last_direction   = 1
        self._last_boost       = True
        self._apply_neutral()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_action(self, action: dict) -> None:
        mario = self._mario
        move  = action.get("move", "RIGHT")
        jump  = action.get("jump", False)
        boost = action.get("boost", True)

        dir_val = MOVE_TO_DIRECTION.get(move, 1)
        self._last_direction = dir_val
        self._last_boost     = boost

        # Horizontal movement
        mario.traits["goTrait"].direction = dir_val
        mario.traits["goTrait"].boost     = boost

        # Jump execution
        if jump:
            if mario.onGround and not self._jump_triggered:
                mario.traits["jumpTrait"].jump(True)
                self._jump_triggered = True
            elif not mario.onGround:
                # In air: hold jump key to reach max jump arc
                mario.traits["jumpTrait"].jump(True)
        else:
            self._jump_triggered = False
            mario.traits["jumpTrait"].jump(False)

    def _apply_coasting(self) -> None:
        """
        When waiting for an AI response, keep moving forward instead of stopping.
        Never stall in mid-air.
        """
        mario = self._mario

        # Maintain horizontal direction (default RIGHT)
        direction = self._last_direction if self._last_direction != 0 else 1
        mario.traits["goTrait"].direction = direction
        mario.traits["goTrait"].boost     = self._last_boost

        # Release jump trigger so we don't jump continuously
        mario.traits["jumpTrait"].jump(False)
        if mario.onGround:
            self._jump_triggered = False

    def _apply_neutral(self) -> None:
        mario = self._mario
        mario.traits["goTrait"].direction = 0
        mario.traits["goTrait"].boost     = False
        mario.traits["jumpTrait"].jump(False)
        self._jump_triggered = False
