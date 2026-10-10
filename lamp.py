"""
lamp.py — lamp module (owner: C)

This file only handles STATE and the MAIN LOOP. It knows nothing about how the
lamp looks; all drawing is delegated to a skin from lamp_skins.py.

Interface:
    lamp.set_light(on: bool)   Set the lamp's target state. Returns immediately; safe to call from another thread.
    lamp.set_skin(skin)        Optional: choose a look (a LampSkin instance). Call before run().
    lamp.set_key_handler(fn)   Optional: forward Y/N presses from this window to the controller.
    lamp.run()                 Open the window and run the pygame main loop (must be called on the main thread).

Standalone test:
    python lamp.py             Press Space to toggle on/off; press Esc or close the window to quit.
"""

from collections.abc import Callable

import pygame
from lamp_skins import LampSkin, GooseneckLamp

# ---------- State ----------
_target = 0.0      # Target brightness: 0 = off, 1 = on (changed by set_light)
_level = 0.0       # Current brightness; moves toward _target each frame to create the fade
FADE_SPEED = 3.0   # Fade speed in brightness units per second (about 1/3 s for a full fade)
FPS = 60

DEFAULT_SKIN = GooseneckLamp
_skin: LampSkin = DEFAULT_SKIN()
_key_handler: Callable[[str], None] | None = None


def set_light(on: bool) -> None:
    """Set the target state. Only updates a number and never draws, so it never blocks."""
    global _target
    _target = 1.0 if on else 0.0


def is_on() -> bool:
    return _target >= 0.5


def set_skin(skin: LampSkin) -> None:
    """Choose which skin draws the lamp. Call before run()."""
    global _skin
    _skin = skin


def set_key_handler(handler: Callable[[str], None] | None) -> None:
    """Forward Y/N key presses to the controller when one is registered."""
    global _key_handler
    _key_handler = handler


def _step_level(level: float, target: float, dt: float) -> float:
    """Move level toward target by at most FADE_SPEED * dt."""
    step = FADE_SPEED * dt
    if level < target:
        return min(target, level + step)
    if level > target:
        return max(target, level - step)
    return level


# ---------- Main loop ----------
def run() -> None:
    """Open the window and run until it is closed or Esc is pressed. Must run on the main thread."""
    global _level
    pygame.init()
    screen = pygame.display.set_mode(_skin.size)
    pygame.display.set_caption(_skin.title)
    _skin.setup()
    clock = pygame.time.Clock()
    t = 0.0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    set_light(not is_on())   # Manual toggle for testing
                elif event.key in (pygame.K_y, pygame.K_n) and _key_handler is not None:
                    _key_handler("y" if event.key == pygame.K_y else "n")

        _level = _step_level(_level, _target, dt)
        _skin.draw(screen, _level, is_on(), t)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run()
