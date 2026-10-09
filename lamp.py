"""
lamp.py — lamp module (owner: C)

Interface:
    lamp.set_light(on: bool)   Set the lamp's target state. Returns immediately; safe to call from another thread.
    lamp.run()                 Open the window and run the pygame main loop (must be called on the main thread).

Standalone test:
    python lamp.py             Press Space to toggle on/off; press Esc or close the window to quit.
"""

import math
import pygame

# ---------- State ----------
_target = 0.0      # Target brightness: 0 = off, 1 = on (changed by set_light)
_level = 0.0       # Current brightness; moves toward _target each frame to create the fade
FADE_SPEED = 3.0   # Fade speed; higher is faster (about 1/3 s for a full fade)

WIDTH, HEIGHT = 480, 600
FPS = 60


def set_light(on: bool) -> None:
    """Set the target state. Only updates a number and never draws, so it never blocks."""
    global _target
    _target = 1.0 if on else 0.0


def is_on() -> bool:
    return _target >= 0.5


# ---------- Drawing helpers ----------
def _mix(c1, c2, t):
    """Linearly interpolate between two colors, with t from 0 to 1."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _draw(screen, font, level, t):
    # Background: cool when off, slightly warm when on
    screen.fill(_mix((18, 20, 28), (48, 40, 30), level))

    shade_top_y, shade_bottom_y = 150, 250
    cx = WIDTH // 2

    # Light cone (semi-transparent, scales with brightness)
    if level > 0.01:
        cone = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        alpha = int(90 * level)
        pygame.draw.polygon(
            cone,
            (255, 220, 140, alpha),
            [(cx - 70, shade_bottom_y), (cx + 70, shade_bottom_y),
             (cx + 190, 500), (cx - 190, 500)],
        )
        screen.blit(cone, (0, 0))

        # Glow around the bulb, with a gentle "breathing" pulse
        glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pulse = 1 + 0.04 * math.sin(t * 3)
        for r, a in ((110, 25), (75, 45), (45, 70)):
            pygame.draw.circle(glow, (255, 210, 120, int(a * level)),
                               (cx, shade_bottom_y), int(r * pulse))
        screen.blit(glow, (0, 0))

    # Desk surface
    pygame.draw.rect(screen, _mix((40, 34, 30), (90, 70, 50), level),
                     (0, 500, WIDTH, HEIGHT - 500))

    # Base and stem
    metal = _mix((70, 72, 80), (150, 140, 120), level)
    pygame.draw.ellipse(screen, metal, (cx - 70, 480, 140, 30))
    pygame.draw.rect(screen, metal, (cx - 5, shade_bottom_y, 10, 235))

    # Bulb
    bulb = _mix((80, 80, 85), (255, 240, 190), level)
    pygame.draw.circle(screen, bulb, (cx, shade_bottom_y + 5), 22)

    # Lampshade (trapezoid)
    shade = _mix((60, 90, 80), (90, 160, 140), level)
    pygame.draw.polygon(
        screen, shade,
        [(cx - 40, shade_top_y), (cx + 40, shade_top_y),
         (cx + 80, shade_bottom_y), (cx - 80, shade_bottom_y)],
    )

    # Status text
    text = "ON  - you're looking at me" if is_on() else "OFF - look at me..."
    label = font.render(text, True, _mix((140, 140, 150), (255, 235, 200), level))
    screen.blit(label, label.get_rect(center=(cx, 555)))


# ---------- Main loop ----------
def run() -> None:
    """Open the window and run until it is closed or Esc is pressed. Must run on the main thread."""
    global _level
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("needyLamp")
    font = pygame.font.SysFont(None, 28)
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

        # Move current brightness smoothly toward the target
        step = FADE_SPEED * dt
        if _level < _target:
            _level = min(_target, _level + step)
        elif _level > _target:
            _level = max(_target, _level - step)

        _draw(screen, font, _level, t)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run()
