"""
lamp.py — lamp module (owner: C)

This file only handles STATE and the MAIN LOOP. It knows nothing about how the
lamp looks; all drawing is delegated to a skin from lamp_skins.py.

Interface:
    lamp.set_light(on: bool)   Set the lamp's target state. Returns immediately; safe to call from another thread.
    lamp.set_skin(skin)        Optional: choose a look (a LampSkin instance). Call before run().
    lamp.set_face_position(x)  Compatibility: normalized horizontal face position in [0, 1].
    lamp.set_key_handler(fn)   Optional: forward Y/N presses from this window to the controller.
    lamp.set_focus(pos)        Optional: where the person's face is, as (x, y) in -1..1 screen space
                               (x: -1 left .. 1 right, y: -1 top .. 1 bottom), or None if no face.
                               Safe to call from another thread. The skin decides how to react.
    lamp.run()                 Open the window and run the pygame main loop (must be called on the main thread).

Standalone test:
    python lamp.py             Press Space to toggle on/off; press Esc or close the window to quit.
                               The mouse stands in for the person's face, so you can test head turning.
"""

from collections.abc import Callable
from pathlib import Path

import pygame
from lamp_skins import LampSkin, GooseneckLamp

# ---------- State ----------
_target = 0.0      # Target brightness: 0 = off, 1 = on (changed by set_light)
_focus = None      # Face position (x, y) in -1..1, or None (changed by set_focus)
_level = 0.0       # Current brightness; moves toward _target each frame to create the fade
FADE_SPEED = 3.0   # Fade speed in brightness units per second (about 1/3 s for a full fade)
_minimized = False # Whether the window is currently minimized/iconified
FPS = 60

DEFAULT_SKIN = GooseneckLamp
_skin: LampSkin = DEFAULT_SKIN()
_key_handler: Callable[[str], None] | None = None


def set_light(on: bool) -> None:
    """Set the target state. Only updates a number and never draws, so it never blocks."""
    global _target
    _target = 1.0 if on else 0.0


def set_focus(pos) -> None:
    """Tell the lamp where the person's face is: (x, y) in -1..1, or None."""
    global _focus
    _focus = None if pos is None else (max(-1.0, min(1.0, pos[0])), max(-1.0, min(1.0, pos[1])))


def set_face_position(x: float | None) -> None:
    """Accept a normalized camera x position from the face-tracking interface."""
    set_focus(None if x is None else (1.0 - 2.0 * x, 0.0))


def is_on() -> bool:
    return _target >= 0.5


def is_minimized() -> bool:
    """Whether the lamp window is currently minimized. Other modules (e.g.
    the camera) can poll this to pause work while nobody can see the lamp."""
    return _minimized


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
def run(mouse_focus: bool = False) -> None:
    """
    Open the window and run until it is closed or Esc is pressed. Must run on the main thread.
    mouse_focus=True makes the mouse act as the person's face (for testing without a camera).
    """
    global _level, _minimized
    pygame.init()
    on_sound = None
    if pygame.mixer.get_init():
        try:
            on_sound = pygame.mixer.Sound(str(Path(__file__).parent / "assets" / "lamp_on.wav"))
        except (pygame.error, OSError) as exc:
            print(f"Lamp sound unavailable: {exc}")
    else:
        print("Lamp sound unavailable: no audio device")
    was_on = False
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
            elif event.type == pygame.MOUSEMOTION and mouse_focus:
                w, h = screen.get_size()
                set_focus((event.pos[0] / w * 2 - 1, event.pos[1] / h * 2 - 1))

        on = is_on()
        if on and not was_on and on_sound is not None:
            on_sound.play()
        was_on = on
        _level = _step_level(_level, _target, dt)
        _skin.set_focus(_focus)
        _skin.draw(screen, _level, on, t)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run(mouse_focus=True)
