
"""
lamp_skins.py — lamp appearances.
 
Everything about how the lamp LOOKS lives here. lamp.py never draws anything
itself; it only tells the active skin the current brightness.
 
To add a new look:
    1. Subclass LampSkin below.
    2. Implement draw().
    3. In lamp.py, call lamp.set_skin(YourSkin()) before lamp.run()
       (or change DEFAULT_SKIN in lamp.py).
"""
 
import math
import pygame
 
 
def mix(c1, c2, t):
    """Linearly interpolate between two RGB colors, with t from 0 to 1."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
 
 
class LampSkin:
    """Base class: the contract every skin must follow."""
 
    size = (480, 600)        # Window size in pixels
    title = "needyLamp"      # Window title
 
    def setup(self) -> None:
        """Called once after pygame.init(). Load fonts and images here."""
 
    def draw(self, screen: pygame.Surface, level: float, on: bool, t: float) -> None:
        """
        Draw one frame.
 
        screen: the pygame surface to draw on
        level:  current brightness, 0.0 (off) to 1.0 (on); already faded smoothly
        on:     the target state (True = should be on)
        t:      seconds since start, for animations
        """
        raise NotImplementedError
 
 
class DeskLamp(LampSkin):
    """Default skin: a simple desk lamp with a light cone and a breathing glow."""
 
    # Colors as (off, on) pairs, so the look can be retuned in one place
    BG = ((18, 20, 28), (48, 40, 30))
    LIGHT = (255, 220, 140)
    GLOW = (255, 210, 120)
    DESK = ((40, 34, 30), (90, 70, 50))
    METAL = ((70, 72, 80), (150, 140, 120))
    BULB = ((80, 80, 85), (255, 240, 190))
    SHADE = ((60, 90, 80), (90, 160, 140))
    TEXT = ((140, 140, 150), (255, 235, 200))
 
    ON_TEXT = "ON  - you're looking at me"
    OFF_TEXT = "OFF - look at me..."
 
    def setup(self):
        self.font = pygame.font.SysFont(None, 28)
 
    def draw(self, screen, level, on, t):
        w, h = self.size
        cx = w // 2
        shade_top_y, shade_bottom_y, desk_y = 150, 250, 500
 
        screen.fill(mix(*self.BG, level))
 
        if level > 0.01:
            # Light cone (semi-transparent, scales with brightness)
            cone = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.polygon(
                cone, (*self.LIGHT, int(90 * level)),
                [(cx - 70, shade_bottom_y), (cx + 70, shade_bottom_y),
                 (cx + 190, desk_y), (cx - 190, desk_y)],
            )
            screen.blit(cone, (0, 0))
 
            # Glow around the bulb, with a gentle "breathing" pulse
            glow = pygame.Surface((w, h), pygame.SRCALPHA)
            pulse = 1 + 0.04 * math.sin(t * 3)
            for r, a in ((110, 25), (75, 45), (45, 70)):
                pygame.draw.circle(glow, (*self.GLOW, int(a * level)),
                                   (cx, shade_bottom_y), int(r * pulse))
            screen.blit(glow, (0, 0))
 
        # Desk surface
        pygame.draw.rect(screen, mix(*self.DESK, level), (0, desk_y, w, h - desk_y))
 
        # Base and stem
        metal = mix(*self.METAL, level)
        pygame.draw.ellipse(screen, metal, (cx - 70, desk_y - 20, 140, 30))
        pygame.draw.rect(screen, metal, (cx - 5, shade_bottom_y, 10, desk_y - shade_bottom_y - 15))
 
        # Bulb
        pygame.draw.circle(screen, mix(*self.BULB, level), (cx, shade_bottom_y + 5), 22)
 
        # Lampshade (trapezoid)
        pygame.draw.polygon(
            screen, mix(*self.SHADE, level),
            [(cx - 40, shade_top_y), (cx + 40, shade_top_y),
             (cx + 80, shade_bottom_y), (cx - 80, shade_bottom_y)],
        )
 
        # Status text
        label = self.font.render(self.ON_TEXT if on else self.OFF_TEXT,
                                 True, mix(*self.TEXT, level))
        screen.blit(label, label.get_rect(center=(cx, 555)))
 
 
class SimpleBulb(LampSkin):
    """Minimal example skin: a single glowing circle. Copy this to start a new look."""
 
    size = (400, 400)
 
    def draw(self, screen, level, on, t):
        screen.fill(mix((10, 10, 15), (40, 35, 20), level))
        center = (self.size[0] // 2, self.size[1] // 2)
        pygame.draw.circle(screen, mix((60, 60, 65), (255, 230, 150), level), center, 80)

