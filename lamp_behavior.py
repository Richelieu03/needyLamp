"""
lamp_behavior.py — how the lamp ACTS (its personality), separate from how it looks.

The behavior only knows two things: whether the lamp is on, and the time.
Each frame it returns a Mood: small offsets and extras that a skin can apply
(tilt the head, hop, glow a little, show "zzz", change the caption).
Skins that don't care can simply ignore it.

What it does:
    Off, just now           sighs and sways ("look at me...")
    Off, a few seconds      every few seconds: looks around, peeks with a
                            tiny flicker, or stretches its neck
    Off, a long time        dozes off: head droops, slow breathing, "zzz"
    Turned on               hops with joy (a bigger startled hop if it was asleep)
    On, for a while         every so often gives a happy little nod

All timings are class constants, so the personality can be tuned in one place.
"""

import math
import random
from dataclasses import dataclass


@dataclass
class Mood:
    bend: float = 0.0           # Extra neck bend in degrees (+ = droop, - = lift)
    tilt: float = 0.0           # Extra shade tilt in degrees (+ = down/forward, - = up/back)
    hop: float = 0.0            # How far the whole lamp is lifted off the desk, in pixels
    peek: float = 0.0           # Small glow while off, 0..1 (a "psst!" flicker)
    zzz: float = 0.0            # How asleep it is, 0..1 (for drawing "zzz")
    message: str | None = None  # Caption to show; None = use the skin's default


def _ease(u):
    """Smooth 0 -> 1 -> 0 envelope over u in [0, 1]."""
    return math.sin(math.pi * max(0.0, min(1.0, u))) ** 2


class IdleBehavior:
    SAD_FOR = 2.0              # Seconds of plain sighing right after being turned off
    DOZE_AFTER = 25.0          # Seconds off before it falls asleep
    IDLE_GAP = (3.0, 6.0)      # Random pause between idle actions while off
    NOD_GAP = (6.0, 10.0)      # Random pause between happy nods while on

    # name: (duration in seconds, caption)
    ACTIONS = {
        "look":    (3.2, "hello? anyone there?"),
        "peek":    (1.0, "psst!"),
        "stretch": (2.4, "*stretches*"),
        "nod":     (1.0, None),
        "wake":    (0.45, None),
        "startle": (0.7, "huh?! oh, it's you!"),
    }
    IDLE_CHOICES = ["look", "look", "peek", "stretch"]

    SAD_TEXT = "OFF - look at me..."
    SLEEP_TEXT = "zzz... (look at me to wake me up)"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.prev_on = None
        self.since = 0.0            # When the on/off state last changed
        self.action = None          # (name, start time)
        self.next_action = 0.0
        self.doze = 0.0             # Smoothed sleepiness, 0..1
        self.last_t = None

    # ---------- Public ----------
    def update(self, on: bool, t: float) -> Mood:
        dt = 0.0 if self.last_t is None else min(t - self.last_t, 1 / 30)
        self.last_t = t

        if on != self.prev_on:
            self._on_state_change(on, t)
        self.prev_on = on

        idle = t - self.since
        self._update_doze(on, idle, dt)
        self._maybe_start_action(on, idle, t)

        mood = Mood()
        self._apply_baseline(mood, on, t)
        self._apply_action(mood, t)
        self._apply_caption(mood, on, idle)
        return mood

    # ---------- State ----------
    def _on_state_change(self, on, t):
        if self.prev_on is not None and on:
            # Big startled hop if it was asleep, otherwise a happy little hop
            self._start("startle" if self.doze > 0.5 else "wake", t)
        else:
            self.action = None
        self.since = t
        gap = self.NOD_GAP if on else self.IDLE_GAP
        self.next_action = t + (gap[0] if on else self.SAD_FOR + gap[0])

    def _update_doze(self, on, idle, dt):
        target = 1.0 if (not on and idle > self.DOZE_AFTER) else 0.0
        rate = 0.35 if target > self.doze else 5.0       # fall asleep slowly, wake fast
        self.doze += (target - self.doze) * min(1.0, rate * dt)

    def _maybe_start_action(self, on, idle, t):
        if self.action is not None:
            name, start = self.action
            if t - start < self.ACTIONS[name][0]:
                return
            self.action = None
        if t < self.next_action or self.doze > 0.2:
            return
        if on:
            self._start("nod", t)
            self.next_action = t + self.rng.uniform(*self.NOD_GAP)
        elif idle > self.SAD_FOR:
            self._start(self.rng.choice(self.IDLE_CHOICES), t)
            self.next_action = t + self.rng.uniform(*self.IDLE_GAP)

    def _start(self, name, t):
        self.action = (name, t)

    # ---------- Building the mood ----------
    def _apply_baseline(self, mood, on, t):
        if on:
            mood.bend += 1.5 * math.sin(t * 2.0)                     # gentle bob
        else:
            awake = 1.0 - self.doze
            mood.bend += 3.0 * awake * math.sin(t * 1.3)             # sigh / sway
            mood.bend += self.doze * (22 + 2.5 * math.sin(t * 1.1))  # droop + slow breathing
            mood.tilt += self.doze * 12
            mood.zzz = self.doze

    def _apply_action(self, mood, t):
        if self.action is None:
            return
        name, start = self.action
        u = (t - start) / self.ACTIONS[name][0]
        if name == "look":
            # Lift the head, glance one way, then the other
            mood.bend -= 14 * _ease(u)
            mood.tilt += 30 * math.sin(2 * math.pi * u) * _ease(u) ** 0.5
        elif name == "peek":
            # Two quick flickers of light and a little head lift
            mood.peek = 0.55 * abs(math.sin(2 * math.pi * u)) * _ease(u) ** 0.3
            mood.bend -= 6 * _ease(u)
        elif name == "stretch":
            # Straighten the neck up, shiver at the top, settle back down
            mood.bend -= 40 * _ease(u)
            mood.tilt -= 15 * _ease(u)
            mood.tilt += 3 * math.sin(t * 40) * _ease((u - 0.3) / 0.4)
        elif name == "nod":
            mood.bend += 6 * math.sin(4 * math.pi * u) * _ease(u)
        elif name == "wake":
            mood.hop = 14 * math.sin(math.pi * min(u, 1.0))
        elif name == "startle":
            mood.hop = 24 * math.sin(math.pi * min(u, 1.0))
            mood.tilt += 10 * math.sin(t * 35) * (1 - u)

    def _apply_caption(self, mood, on, idle):
        if self.action is not None and self.ACTIONS[self.action[0]][1]:
            mood.message = self.ACTIONS[self.action[0]][1]
        elif not on and self.doze > 0.5:
            mood.message = self.SLEEP_TEXT
        elif not on:
            mood.message = self.SAD_TEXT