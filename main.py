"""
main.py — JevMario entry point.

Run normally (keyboard control):
    python main.py

Run with Jev AI control:
    python main.py --ai

Run with the built-in rule-based model (no API key needed):
    python main.py --ai --mode rule
"""

import sys
import argparse

import pygame
from classes.Dashboard import Dashboard
from classes.Level import Level
from classes.Menu import Menu
from classes.Sound import Sound
from entities.Mario import Mario


windowSize = 640, 480


def parse_args():
    parser = argparse.ArgumentParser(description="JevMario")
    parser.add_argument("--ai",   action="store_true", help="Enable Jev AI control")
    parser.add_argument(
        "--mode",
        choices=["jev", "rule"],
        default=None,
        help="AI backend: 'jev' (default, uses API) or 'rule' (no API needed)",
    )
    return parser.parse_args()


def build_ai_controller(mario, mode: str):
    """Construct and return a ready AIController."""
    from ai.config import AI_CONFIG
    from ai.controller import AIController
    from ai.decision_model import JevDecisionModel, RuleBasedModel

    resolved_mode = mode or AI_CONFIG.get("ai_mode", "jev")
    if resolved_mode == "rule":
        print("[AI] Using rule-based model (no Jev API calls).", file=sys.stderr)
        model = RuleBasedModel()
    else:
        print("[AI] Using Jev API model.", file=sys.stderr)
        model = JevDecisionModel(
            max_duration=AI_CONFIG["max_action_duration_frames"]
        )

    return AIController(mario, model)


def main():
    args = parse_args()
    use_ai = args.ai

    pygame.mixer.pre_init(44100, -16, 2, 4096)
    pygame.init()
    screen = pygame.display.set_mode(windowSize)
    max_frame_rate = 60

    dashboard = Dashboard("./img/font.png", 8, screen)
    sound = Sound()
    level = Level(screen, sound, dashboard)
    menu = Menu(screen, dashboard, level, sound)

    while not menu.start:
        menu.update()

    mario = Mario(0, 0, level, screen, dashboard, sound)
    clock = pygame.time.Clock()

    # --- AI setup ---
    ai_controller = None
    debug_overlay = None

    if use_ai:
        ai_controller = build_ai_controller(mario, args.mode)
        ai_controller.start()

        # Disable keyboard input so AI has full control
        mario.input.ai_mode = True

        from ai.config import AI_CONFIG
        if AI_CONFIG["debug_ai_state"]:
            from ai.debug_overlay import DebugOverlay
            debug_overlay = DebugOverlay(screen)

    # --- Game loop ---
    frame = 0
    prev_restart = mario.restart  # track restart state to detect death

    while not mario.restart:
        pygame.display.set_caption(
            "Super Mario [{:d} FPS]{}".format(
                int(clock.get_fps()),
                " [JEV AI]" if use_ai else ""
            )
        )

        if mario.pause:
            mario.pauseObj.update()
        else:
            # AI tick must run BEFORE mario.update() so traits are set first
            if ai_controller is not None:
                ai_controller.tick(frame)

            level.drawLevel(mario.camera)
            dashboard.update()
            mario.update()

            # Debug overlay drawn last (on top of everything)
            if debug_overlay is not None:
                debug_overlay.draw(ai_controller.debug_info)

        pygame.display.update()
        clock.tick(max_frame_rate)
        frame += 1

    # Cleanup
    if ai_controller is not None:
        ai_controller.stop()

    return 'restart'


if __name__ == "__main__":
    exitmessage = 'restart'
    while exitmessage == 'restart':
        exitmessage = main()
