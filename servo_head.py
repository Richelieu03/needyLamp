"""
servo_head.py — send the lamp's head angle to the Arduino over USB serial.

Interface:
    servo_head.connect(port=None)   Open the serial port (auto-detects /dev/cu.usbmodem* / usbserial*).
    servo_head.look_at(face_x)      face_x in 0..1 from brain.locate_face(), or None to recenter.
    servo_head.set_angle(angle)     Send a raw angle (clamped to MIN_ANGLE..MAX_ANGLE).

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
INVERT = False      # set True if the head turns the wrong way

_port = None
_last_sent = None


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
    set_angle(CENTER)


def set_angle(angle):
    """Send a target angle; skips repeats so the serial line stays quiet."""
    global _last_sent
    if _port is None:
        return
    angle = int(max(MIN_ANGLE, min(MAX_ANGLE, angle)))
    if angle != _last_sent:
        _port.write(f"{angle}\n".encode())
        _last_sent = angle


def look_at(face_x):
    """Turn toward a face at face_x (0 = left edge of the camera image, 1 = right edge)."""
    if face_x is None:
        set_angle(CENTER)
        return
    if INVERT:
        face_x = 1 - face_x
    set_angle(MIN_ANGLE + face_x * (MAX_ANGLE - MIN_ANGLE))


if __name__ == "__main__":
    connect()
    print("Connected. Sweeping...")
    for angle in (CENTER, MIN_ANGLE, CENTER, MAX_ANGLE, CENTER):
        print("angle:", angle)
        set_angle(angle)
        time.sleep(1.5)
    print("Done.")
