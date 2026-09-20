"""
ai/debug_overlay.py
-------------------
Optional in-game debug overlay.

Renders a semi-transparent panel in the top-right corner showing the AI's
current state:

    ┌────────────────────────┐
    │ AI STATE               │
    │ Frame: 1204            │
    │ Life:  0               │
    │                        │
    │ Action: RIGHT          │
    │ Jump:   YES            │
    │ Boost:  NO             │
    │ Frames: 4/8 left       │
    │                        │
    │ Latency: 123ms         │
    │ Decisions: 42          │
    │ Deaths: 1              │
    └────────────────────────┘

Rendering is entirely separate from gameplay logic.
"""

from __future__ import annotations

import pygame

PANEL_COLOR = (0, 0, 0, 160)        # semi-transparent black
TEXT_COLOR  = (255, 255, 255)
LABEL_COLOR = (180, 230, 255)
WIDTH  = 200
HEIGHT = 210
MARGIN = 8


class DebugOverlay:
    """
    Renders AI debug info onto the game screen.

    Args:
        screen: The Pygame display surface.
    """

    def __init__(self, screen: pygame.Surface):
        self._screen = screen
        self._font = pygame.font.SysFont("monospace", 12)
        self._panel = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def draw(self, debug_info: dict) -> None:
        """Draw the debug panel. Call after all game rendering."""
        panel = self._panel
        panel.fill(PANEL_COLOR)

        action = debug_info.get("action", {})
        move   = action.get("move", "?")
        jump   = "YES" if action.get("jump") else "NO"
        boost  = "YES" if action.get("boost") else "NO"
        dur    = action.get("duration_frames", 0)
        left   = debug_info.get("frames_left", 0)
        lat    = debug_info.get("latency_ms", 0)
        decs   = debug_info.get("decisions", 0)
        deaths = debug_info.get("deaths", 0)
        frame  = debug_info.get("frame", 0)
        life   = debug_info.get("life", 0)

        lines = [
            ("AI STATE",       LABEL_COLOR),
            (f"Frame: {frame}", TEXT_COLOR),
            (f"Life:  {life}",  TEXT_COLOR),
            ("",               TEXT_COLOR),
            (f"Move:   {move}", TEXT_COLOR),
            (f"Jump:   {jump}", TEXT_COLOR),
            (f"Boost:  {boost}", TEXT_COLOR),
            (f"Dur:    {left}/{dur}", TEXT_COLOR),
            ("",               TEXT_COLOR),
            (f"Latency:{lat:.0f}ms", TEXT_COLOR),
            (f"Decisions:{decs}", TEXT_COLOR),
            (f"Deaths:{deaths}", TEXT_COLOR),
        ]

        y = MARGIN
        for text, color in lines:
            surf = self._font.render(text, True, color)
            panel.blit(surf, (MARGIN, y))
            y += 16

        sw = self._screen.get_width()
        self._screen.blit(panel, (sw - WIDTH - 4, 4))
