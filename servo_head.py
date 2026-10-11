"""
servo_head.py — send the lamp's head angle to the Arduino over USB serial.

Interface:
    servo_head.connect(port=None)   Open the serial port (auto-detects /dev/cu.usbmodem* / usbserial*).
    servo_head.look_at(face_x)      face_x in 0..1 from brain.locate_face(), or None if no face.
    servo_head.set_angle(angle)     Send a raw angle (clamped to MIN_ANGLE..MAX_ANGLE).

Smooth following:
    - face positions are smoothed (exponential moving average) so detection noise doesn't jitter the head
    - changes smaller than DEAD_ZONE degrees are ignored
    - if the face disappears, the head holds its position for HOLD_SECONDS before recentering,
      so a single missed frame doesn't make it snap back and forth

Self-test (close the Arduino IDE Serial Monitor first, it locks the port):
    python3 servo_head.py           Sweeps the head left, center, right.

Requires:  pip3 install pyserial
"""

import glob
import time

import serial

BAUD = 115200
CENTER = 90
MIN_ANGLE = 30
MAX_ANGLE = 150
INVERT = False       # set True if the head turns the wrong way

SMOOTHING = 0.35     # 0..1: higher follows faster, lower is calmer
DEAD_ZONE = 4        # ignore changes smaller than this (degrees)
HOLD_SECONDS = 1.5   # keep looking at the last spot this long after the face is lost

_port = None
_last_sent = None
_smooth_x = None     # smoothed face position (0..1)
_last_seen = 0.0     # time the face was last seen


def _find_port():
    candidates = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")
                        + glob.glob("/dev/cu.wchusbserial*"))
    if not candidates:
        raise RuntimeError("No Arduino found. Is it plugged in with a data USB cable?")
    return candidates[0]


def connect(port=None):
    """Open the serial port. The Arduino resets when the port opens, so wait for it to boot."""
    global _port
    _port = serial.Serial(port or _find_port(), BAUD, timeout=1)
    time.sleep(2)
    set_angle(CENTER, force=True)


def set_angle(angle, force=False):
    """Send a target angle. Small changes (< DEAD_ZONE) are skipped unless force=True."""
    global _last_sent
    if _port is None:
        return
    angle = int(max(MIN_ANGLE, min(MAX_ANGLE, angle)))
    if _last_sent is not None and not force and abs(angle - _last_sent) < DEAD_ZONE:
        return
    if angle != _last_sent:
        _port.write(f"{angle}\n".encode())
        _last_sent = angle


def look_at(face_x):
    """Turn toward a face at face_x (0 = left edge of the camera image, 1 = right edge)."""
    global _smooth_x, _last_seen
    now = time.monotonic()

    if face_x is None:
        # Face lost: hold for a moment, then go back to the centre
        if now - _last_seen > HOLD_SECONDS:
            _smooth_x = None
            set_angle(CENTER, force=True)
        return

    _last_seen = now
    if INVERT:
        face_x = 1 - face_x
    _smooth_x = face_x if _smooth_x is None else _smooth_x + SMOOTHING * (face_x - _smooth_x)
    set_angle(MIN_ANGLE + _smooth_x * (MAX_ANGLE - MIN_ANGLE))


if __name__ == "__main__":
    connect()
    print("Connected. Sweeping...")
    for angle in (CENTER, MIN_ANGLE, CENTER, MAX_ANGLE, CENTER):
        print("angle:", angle)
        set_angle(angle, force=True)
        time.sleep(1.5)
    print("Done.")