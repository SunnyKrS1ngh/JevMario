"""
ai/observation.py
-----------------
Observation Layer — extracts and normalises the Mario game's internal state
into a clean, AI-consumable JSON dictionary.

No game logic lives here; this module only reads from existing game objects.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entities.Mario import Mario

# Scan radius for nearby entities (pixels)
NEARBY_RADIUS_X = 384   # ~12 tiles
NEARBY_RADIUS_Y = 192   # ~6 tiles

# How many tiles ahead to scan in the tile map for obstacles
TILE_SCAN_AHEAD = 10


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class ObservationProvider:
    """Abstract base — produce a state dict from whatever source is available."""

    def get_state(self) -> dict:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Internal state provider (reads game objects directly)
# ---------------------------------------------------------------------------

class InternalStateProvider(ObservationProvider):
    """
    Reads Mario's internal state and converts it to a structured observation.

    Args:
        mario: The Mario entity (entities.Mario.Mario).
    """

    def __init__(self, mario: "Mario"):
        self._mario = mario

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_state(self) -> dict:
        mario = self._mario
        level = mario.levelObj

        player     = self._player_state(mario)
        nearby     = self._nearby_state(mario, level)
        obstacles  = self._tile_obstacles(mario, level)
        camera     = self._camera_state(mario)
        level_info = self._level_state(mario, level)

        return {
            "player": player,
            "nearby": nearby,
            "obstacles": obstacles,
            "camera": camera,
            "level": level_info,
        }

    # ------------------------------------------------------------------
    # Sub-sections
    # ------------------------------------------------------------------

    def _player_state(self, mario) -> dict:
        power_map = {0: "small", 1: "big", 2: "fire"}
        return {
            "x": mario.rect.x,
            "y": mario.rect.y,
            "vx": round(mario.vel.x, 3),
            "vy": round(mario.vel.y, 3),
            "on_ground": mario.onGround,
            "in_air": mario.inAir,
            "power": power_map.get(mario.powerUpState, "small"),
            "invincible": mario.invincibilityFrames > 0,
            "tile_x": mario.rect.x // 32,
            "tile_y": mario.rect.y // 32,
        }

    def _nearby_state(self, mario, level) -> dict:
        mx, my = mario.rect.x, mario.rect.y
        enemies = []
        items = []

        for ent in level.entityList:
            dx = ent.rect.x - mx
            dy = ent.rect.y - my

            if abs(dx) > NEARBY_RADIUS_X or abs(dy) > NEARBY_RADIUS_Y:
                continue

            entry = {
                "relative_x": int(dx),
                "relative_y": int(dy),
            }

            ent_type   = getattr(ent, "type", "")
            class_name = ent.__class__.__name__

            if ent_type == "Mob":
                entry["enemy_type"] = class_name.lower()
                entry["alive"]      = getattr(ent, "alive", False)
                vel = getattr(ent, "vel", None)
                entry["vx"] = round(vel.x, 3) if vel is not None else 0
                if entry["alive"]:
                    enemies.append(entry)

            elif ent_type == "Item":
                entry["item_type"] = class_name.lower()
                items.append(entry)

        enemies.sort(key=lambda e: abs(e["relative_x"]))
        items.sort(key=lambda e: abs(e["relative_x"]))

        return {
            "enemies": enemies[:5],
            "items": items[:3],
        }

    def _tile_obstacles(self, mario, level) -> dict:
        """
        Scan the tile map and entity list for obstacles (pipes, walls, pits)
        directly ahead of Mario.

        Accurately distinguishes:
        - Ground under Mario's feet (not an obstacle)
        - Floating blocks Mario can walk under (not an obstacle)
        - Solid pipes and walls that block Mario's horizontal body (obstacle)
        - Pits where ground has ended (gap)
        """
        tile_map = level.level
        if tile_map is None:
            return {}

        ground_y = mario.rect.bottom
        ground_row = ground_y // 32
        mario_tile_x = mario.rect.x // 32

        ahead_tiles = []
        wall_ahead = False
        wall_height = 0
        wall_dist_px = None
        gap_ahead = False
        gap_dist_px = None

        total_cols = len(tile_map[0]) if tile_map else 0

        for col_offset in range(1, TILE_SCAN_AHEAD + 1):
            col = mario_tile_x + col_offset
            if col < 0 or col >= total_cols:
                continue

            # Check gap (pit where there is no solid ground at ground level)
            if 0 <= ground_row < len(tile_map):
                try:
                    if tile_map[ground_row][col].rect is None and not gap_ahead:
                        gap_ahead = True
                        gap_dist_px = max(0, col * 32 - mario.rect.right)
                except IndexError:
                    pass

            # Check for solid tiles that block horizontal movement:
            # Must be above the ground Mario is walking on (top < ground_y)
            # AND must intersect Mario's vertical height (top < mario.bottom and bottom > mario.top)
            blocking_tiles = []
            col_solid_tiles = []

            for row in range(0, min(len(tile_map), ground_row)):
                try:
                    t = tile_map[row][col]
                except IndexError:
                    continue

                if t.rect is not None:
                    col_solid_tiles.append(t)
                    # Check if tile blocks Mario horizontally
                    if t.rect.top < mario.rect.bottom and t.rect.bottom > mario.rect.top:
                        blocking_tiles.append(t)

            if blocking_tiles and not wall_ahead:
                wall_ahead = True
                wall_dist_px = max(0, col * 32 - mario.rect.right)
                min_top = min(t.rect.top for t in col_solid_tiles)
                wall_height = max(1, (ground_y - min_top) // 32)

            for t in blocking_tiles:
                ahead_tiles.append({
                    "col_offset": col_offset,
                    "relative_x": max(0, col * 32 - mario.rect.right),
                    "rect_y": t.rect.y,
                })

        return {
            "wall_ahead":    wall_ahead,
            "wall_height":   wall_height,
            "wall_dist_px":  wall_dist_px,
            "gap_ahead":     gap_ahead,
            "gap_dist_px":   gap_dist_px,
            "ahead_tiles":   ahead_tiles[:10],
        }

    def _camera_state(self, mario) -> dict:
        cam = mario.camera
        return {
            "x": int(cam.x),
            "pos_x": round(cam.pos.x, 3),
        }

    def _level_state(self, mario, level) -> dict:
        level_length_px = level.levelLength * 32
        remaining = max(0, level_length_px - mario.rect.x)
        return {
            "level_length_px": level_length_px,
            "mario_world_x":   mario.rect.x,
            "remaining_distance": remaining,
        }
