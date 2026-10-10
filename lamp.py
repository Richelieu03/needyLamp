"""
lamp.py — lamp module (owner: C)

This file only handles STATE and the MAIN LOOP. It knows nothing about how the
lamp looks; all drawing is delegated to a skin from lamp_skins.py.

Interface:
    lamp.set_light(on: bool)   Set the lamp's target state. Returns immediately; safe to call from another thread.
    lamp.set_face_position(x)  Normalized horizontal face position in [0, 1], or None if no face.
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
_minimized = False # Whether the window is currently minimized/iconified
_face_x = None     # Normalized horizontal face position [0, 1]; None = no face detected
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


def is_minimized() -> bool:
    """Whether the lamp window is currently minimized. Other modules (e.g.
    the camera) can poll this to pause work while nobody can see the lamp."""
    return _minimized


def set_face_position(x: float | None) -> None:
    """Report where the tracked face is, horizontally, in the camera frame
    (0 = left edge, 1 = right edge), or None if no face is currently
    detected. Only updates a number and never draws, so it never blocks;
    safe to call from another thread."""
    global _face_x
    _face_x = x


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
    global _level, _minimized
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
            elif event.type == pygame.WINDOWMINIMIZED:
                _minimized = True
            elif event.type in (pygame.WINDOWRESTORED, pygame.WINDOWSHOWN):
                # On macOS, restoring from the Dock fires WINDOWSHOWN rather
                # than WINDOWRESTORED (which never arrives there); other
                # platforms may use either, so we clear on both.
                _minimized = False

        _level = _step_level(_level, _target, dt)
        _skin.draw(screen, _level, is_on(), t, _face_x)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run()
