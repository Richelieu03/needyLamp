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


def lerp(a, b, t):
    """Linearly interpolate between two numbers, with t from 0 to 1."""
    return a + (b - a) * t


def bezier(p0, p1, p2, t):
    """Point on a quadratic Bezier curve at t (0..1)."""
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


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
    """Simple upright desk lamp with a light cone and a breathing glow."""

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

    def draw_text(self, screen, level, on):
        label = self.font.render(self.ON_TEXT if on else self.OFF_TEXT,
                                 True, mix(*self.TEXT, level))
        screen.blit(label, label.get_rect(center=(self.size[0] // 2, 555)))

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

        self.draw_text(screen, level, on)


class GooseneckLamp(DeskLamp):
    """
    Gooseneck lamp: a tapered curved neck and a bell-shaped shade.

    Its pose follows the on/off state with a springy motion: when on, the head
    lifts (with a small bounce) and aims the light at the desk; when off, the
    neck sags, the head droops and it sways gently, as if sighing.
    Colors and text are inherited from DeskLamp.

    Rendering tricks that keep it soft rather than stiff:
      - the lamp is drawn on a 2x canvas and smoothly scaled down (anti-aliasing)
      - light is shrunk to 1/8 size and scaled back up, which blurs its edges
    """

    DESK_Y = 500
    BASE_POS = (150, 488)                  # Center of the base on the desk

    # Pose as (off, on) pairs — tweak these to change the posture
    NECK_CTRL = ((125, 330), (100, 220))   # Bezier control point: how the neck bends
    HEAD_POS = ((225, 282), (250, 172))    # Where the neck ends (the joint at the shade)
    HEAD_ANGLE = (108, 62)                 # Shade direction in degrees (90 = straight down)

    NECK_BASE_R = 9.0                      # Neck radius at the base
    NECK_TIP_R = 5.5                       # Neck radius at the head
    NECK_SEGMENTS = 140

    SHADE_LEN = 62                         # Shade length from joint to opening
    SHADE_BACK = 11                        # Half-width at the back of the shade
    SHADE_MOUTH = 44                       # Half-width at the opening

    SPRING_K = 55.0                        # Spring stiffness (higher = snappier)
    SPRING_D = 9.0                         # Damping (lower = more bounce)

    SUPERSAMPLE = 2                        # Draw at 2x, then scale down
    BLUR = 8                               # Light is shrunk by this factor to blur it

    INSIDE = ((30, 32, 36), (255, 236, 180))   # Inside of the shade (off, on)

    def setup(self):
        super().setup()
        w, h = self.size
        s = self.SUPERSAMPLE
        self.canvas = pygame.Surface((w * s, h * s))
        self.pose = 0.0
        self.vel = 0.0
        self.last_t = None
        self._build_shade_shapes()

    # ---------- Shape helpers (shade-local coordinates, opening along +x) ----------
    def _half_width(self, x):
        u = x / self.SHADE_LEN
        return self.SHADE_BACK + (self.SHADE_MOUTH - self.SHADE_BACK) * u ** 1.7

    def _build_shade_shapes(self):
        n = 16
        xs = [self.SHADE_LEN * i / n for i in range(n + 1)]
        top = [(x, -self._half_width(x)) for x in xs]
        bottom = [(x, self._half_width(x)) for x in xs]
        cap = [(-self.SHADE_BACK * 0.9 * math.sin(a), self.SHADE_BACK * math.cos(a))
               for a in (math.pi * i / 10 for i in range(1, 10))]
        self.shade_outline = top + bottom[::-1] + cap

        # Highlight band along the top, shadow band along the bottom
        inner = xs[2:-1]
        self.shade_highlight = ([(x, -self._half_width(x) * 0.88) for x in inner] +
                                [(x, -self._half_width(x) * 0.6) for x in inner[::-1]])
        self.shade_shadow = ([(x, self._half_width(x) * 0.55) for x in inner] +
                             [(x, self._half_width(x) * 0.95) for x in inner[::-1]])

        self.mouth = [(self.SHADE_LEN + 7 * math.cos(a), self.SHADE_MOUTH * math.sin(a))
                      for a in (2 * math.pi * i / 28 for i in range(28))]
        self.bulb_shape = [(self.SHADE_LEN - 0.5 + 4 * math.cos(a), 17 * math.sin(a))
                           for a in (2 * math.pi * i / 20 for i in range(20))]

    # ---------- Motion ----------
    def _step_pose(self, on, t):
        """Spring the pose toward 1 (on) or 0 (off); slight overshoot = lively bounce."""
        dt = 0.0 if self.last_t is None else min(t - self.last_t, 1 / 30)
        self.last_t = t
        target = 1.0 if on else 0.0
        acc = self.SPRING_K * (target - self.pose) - self.SPRING_D * self.vel
        self.vel += acc * dt
        self.pose += self.vel * dt
        return self.pose

    # ---------- Light ----------
    def _light_layer(self, to_world, angle, level, desk_y):
        """Cone, desk pool and ambient glow at design size (blurred later)."""
        w, h = self.size
        q = 1
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        Q = lambda pt: pt

        def ray_to_desk(pt, ang):
            dy = math.sin(ang)
            length = (desk_y - pt[1]) / dy if dy > 0.05 else 700
            length = min(length, 900)
            return (pt[0] + math.cos(ang) * length, pt[1] + dy * length)

        mouth_l = to_world(self.SHADE_LEN, -self.SHADE_MOUTH)
        mouth_r = to_world(self.SHADE_LEN, self.SHADE_MOUTH)
        mouth_c = to_world(self.SHADE_LEN, 0)

        # Ambient warm glow around the head
        for r, alpha in ((170, 8), (120, 10), (75, 12)):
            pygame.draw.circle(surf, (*self.GLOW, int(alpha * level)), Q(mouth_c), r * q)

        # Layered cone: wide and faint outside, narrower and brighter inside
        for spread, alpha in ((0.42, 22), (0.30, 30), (0.18, 38)):
            far_l = ray_to_desk(mouth_l, angle - spread)
            far_r = ray_to_desk(mouth_r, angle + spread)
            pygame.draw.polygon(surf, (*self.LIGHT, int(alpha * level)),
                                [Q(mouth_l), Q(far_l), Q(far_r), Q(mouth_r)])

        # Pool of light where the shade's axis hits the desk
        if math.sin(angle) > 0.2:
            hit_x = mouth_c[0] + (desk_y - mouth_c[1]) * math.cos(angle) / math.sin(angle)
            for rw, alpha in ((280, 30), (180, 45), (100, 60)):
                pygame.draw.ellipse(surf, (*self.LIGHT, int(alpha * level)),
                                    ((hit_x - rw / 2) * q, (desk_y + 4) * q,
                                     rw * q, rw * 0.2 * q))
        return surf

    def _bloom_layer(self, center, level, t):
        """Soft glow over the bulb at design size (blurred later)."""
        w, h = self.size
        q = 1
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pulse = 1 + 0.06 * math.sin(t * 3)
        for r, alpha in ((60, 30), (38, 55), (22, 90)):
            pygame.draw.circle(surf, (*self.GLOW, int(alpha * level)),
                               (center[0] * q, center[1] * q), r * pulse * q)
        return surf

    def _blur_to_canvas(self, surf):
        """Cheap blur: shrink a layer, then scale it up to canvas size."""
        w, h = self.size
        S = self.SUPERSAMPLE
        small = pygame.transform.smoothscale(surf, (w // self.BLUR, h // self.BLUR))
        return pygame.transform.smoothscale(small, (w * S, h * S))

    # ---------- Frame ----------
    def draw(self, screen, level, on, t):
        w, h = self.size
        S = self.SUPERSAMPLE
        desk_y = self.DESK_Y
        c = self.canvas
        P = lambda pt: (pt[0] * S, pt[1] * S)

        # ----- Pose for this frame -----
        p = self._step_pose(on, t)
        sway = (1 - level) * 2.0 * math.sin(t * 1.3)        # idle sigh when off
        bob = 3 * level * math.sin(t * 2)                    # gentle bob when on
        p0 = (self.BASE_POS[0], self.BASE_POS[1] - 8)
        p1 = (lerp(self.NECK_CTRL[0][0], self.NECK_CTRL[1][0], p),
              lerp(self.NECK_CTRL[0][1], self.NECK_CTRL[1][1], p))
        head = (lerp(self.HEAD_POS[0][0], self.HEAD_POS[1][0], p) + sway,
                lerp(self.HEAD_POS[0][1], self.HEAD_POS[1][1], p) + bob)
        angle = math.radians(lerp(*self.HEAD_ANGLE, p) + sway * 1.5)
        ca, sa = math.cos(angle), math.sin(angle)

        def to_world(x, y):
            """Convert a point from shade-local coordinates to design coordinates."""
            return (head[0] + x * ca - y * sa, head[1] + x * sa + y * ca)

        # ----- Background and desk -----
        c.fill(mix(*self.BG, level))
        desk = mix(*self.DESK, level)
        pygame.draw.rect(c, desk, (0, desk_y * S, w * S, (h - desk_y) * S))
        pygame.draw.rect(c, mix(desk, (255, 255, 255), 0.08), (0, desk_y * S, w * S, 2 * S))

        # ----- Soft light -----
        if level > 0.01:
            light = self._light_layer(to_world, angle, level, desk_y)
            c.blit(self._blur_to_canvas(light), (0, 0))

        # ----- Base -----
        metal = mix(*self.METAL, level)
        metal_dark = mix(metal, (0, 0, 0), 0.35)
        metal_hi = mix(metal, (255, 255, 255), 0.35)
        bx, by = self.BASE_POS
        pygame.draw.ellipse(c, mix(desk, (0, 0, 0), 0.35), ((bx - 72) * S, (by - 8) * S, 144 * S, 24 * S))
        pygame.draw.ellipse(c, metal_dark, ((bx - 64) * S, (by - 14) * S, 128 * S, 26 * S))
        pygame.draw.ellipse(c, metal, ((bx - 60) * S, (by - 17) * S, 120 * S, 22 * S))

        # ----- Tapered neck: dark rim, body, highlight -----
        n = self.NECK_SEGMENTS
        pts = [(bezier(p0, p1, head, i / n), lerp(self.NECK_BASE_R, self.NECK_TIP_R, i / n))
               for i in range(n + 1)]
        for pt, r in pts:
            pygame.draw.circle(c, metal_dark, P(pt), r * S)
        for pt, r in pts:
            pygame.draw.circle(c, metal, P((pt[0] - r * 0.15, pt[1] - r * 0.1)), r * 0.78 * S)
        pygame.draw.lines(c, metal_hi, False,
                          [P((pt[0] - r * 0.38, pt[1] - r * 0.25)) for pt, r in pts], int(2.2 * S))

        # Joint between neck and shade
        pygame.draw.circle(c, metal_dark, P(head), 11 * S)
        pygame.draw.circle(c, metal, P(head), 9 * S)
        pygame.draw.circle(c, metal_hi, P((head[0] - 3, head[1] - 3)), 3 * S)

        # ----- Shade -----
        shade = mix(*self.SHADE, level)
        shade_dark = mix(shade, (0, 0, 0), 0.3)
        shade_hi = mix(shade, (255, 255, 255), 0.3)
        world = lambda shape: [P(to_world(x, y)) for x, y in shape]
        pygame.draw.polygon(c, shade, world(self.shade_outline))
        pygame.draw.polygon(c, shade_dark, world(self.shade_shadow))
        pygame.draw.polygon(c, shade_hi, world(self.shade_highlight))

        # Opening: the inside glows when lit, plus a light rim
        pygame.draw.polygon(c, mix(*self.INSIDE, level), world(self.mouth))
        pygame.draw.lines(c, shade_hi, True, world(self.mouth), 2 * S)

        # Bulb seen through the opening: a small ellipse inside the mouth,
        # so it always stays within the shade
        bulb = to_world(self.SHADE_LEN, 0)
        pygame.draw.polygon(c, mix(*self.BULB, level), world(self.bulb_shape))

        # ----- Bloom over the bulb -----
        if level > 0.01:
            bloom = self._bloom_layer(bulb, level, t)
            c.blit(self._blur_to_canvas(bloom), (0, 0))

        # ----- Scale the 2x canvas down to the window (anti-aliasing) -----
        screen.blit(pygame.transform.smoothscale(c, (w, h)), (0, 0))
        self.draw_text(screen, level, on)


class ImageLamp(LampSkin):
    """
    Easiest skin: two pictures, one for OFF and one for ON.
    The fade is done by blending the ON picture over the OFF one.

    Put two images of the same size in an assets/ folder, e.g.
        assets/lamp_off.png   assets/lamp_on.png
    then in lamp.py:  DEFAULT_SKIN = ImageLamp
    """

    OFF_IMAGE = "assets/lamp_off.png"
    ON_IMAGE = "assets/lamp_on.png"

    def setup(self):
        size = pygame.display.get_surface().get_size()
        self.off_img = pygame.transform.smoothscale(
            pygame.image.load(self.OFF_IMAGE).convert_alpha(), size)
        self.on_img = pygame.transform.smoothscale(
            pygame.image.load(self.ON_IMAGE).convert_alpha(), size)

    def draw(self, screen, level, on, t):
        screen.fill((0, 0, 0))
        screen.blit(self.off_img, (0, 0))
        self.on_img.set_alpha(int(255 * level))   # fade ON picture in/out
        screen.blit(self.on_img, (0, 0))


class SimpleBulb(LampSkin):
    """Minimal example skin: a single glowing circle. Copy this to start a new look."""

    size = (400, 400)

    def draw(self, screen, level, on, t):
        screen.fill(mix((10, 10, 15), (40, 35, 20), level))
        center = (self.size[0] // 2, self.size[1] // 2)
        pygame.draw.circle(screen, mix((60, 60, 65), (255, 230, 150), level), center, 80)