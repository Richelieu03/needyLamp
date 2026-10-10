"""
face_tracker.py — find where the person's face is in a camera frame.

Runs locally with OpenCV's built-in face detector: no network, a few
milliseconds per frame. It only answers "where is the face", not "are they
looking" (that is still brain's job).

Interface:
    face_tracker.find_face(frame: str) -> (x, y) | None
        frame: base64 JPEG from camera.get_frame()
        returns the face center in -1..1 screen space, matching lamp.set_focus():
            x: -1 = your left side of the screen .. 1 = your right side
            y: -1 = top .. 1 = bottom
        or None if no face is found.

Self-test:
    python face_tracker.py     Prints the face position once per second.
"""

import base64

import cv2
import numpy as np

_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def find_face(frame: str):
    """Return the center of the largest face as (x, y) in -1..1, or None."""
    data = np.frombuffer(base64.b64decode(frame), np.uint8)
    gray = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return None
    faces = _detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    img_h, img_w = gray.shape
    cx = (x + w / 2) / img_w * 2 - 1
    cy = (y + h / 2) / img_h * 2 - 1
    # The camera faces you, so its left is your right: flip x to match the screen
    return (-cx, cy)


if __name__ == "__main__":
    import time
    import camera

    while True:
        print("face:", find_face(camera.get_frame()))
        time.sleep(1)