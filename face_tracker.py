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
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import cv2
import numpy as np

# As of OpenCV 5.0, the PyPI wheels (opencv-python / -headless / -contrib)
# no longer bundle the Haar cascade XML files, so cv2.data.haarcascades is
# an empty directory. Download the file once from OpenCV's own repo and
# cache it locally - same pattern as the MediaPipe model in brain.py.
CASCADE_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/"
    "haarcascade_frontalface_default.xml"
)
DEFAULT_CASCADE_PATH = Path.home() / ".cache" / "needyLamp" / "haarcascade_frontalface_default.xml"


def _cascade_file() -> Path:
    bundled = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    if bundled.is_file():
        return bundled

    path = DEFAULT_CASCADE_PATH
    if path.is_file():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Haar cascade model once to {path} ...", flush=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary_path = Path(output.name)
            with urlopen(CASCADE_URL, timeout=30) as response:
                shutil.copyfileobj(response, output)
        if temporary_path.stat().st_size < 10_000:
            raise RuntimeError("Downloaded Haar cascade file is incomplete")
        temporary_path.replace(path)
    except (OSError, URLError, TimeoutError) as exc:
        raise RuntimeError(
            "Could not download the Haar cascade model. Download it from "
            f"{CASCADE_URL} and place it at {path}."
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return path


@lru_cache(maxsize=1)
def _get_detector() -> cv2.CascadeClassifier:
    detector = cv2.CascadeClassifier(str(_cascade_file()))
    if detector.empty():
        raise RuntimeError("Failed to load the Haar cascade face detector")
    return detector


def find_face(frame: str):
    """Return the center of the largest face as (x, y) in -1..1, or None."""
    data = np.frombuffer(base64.b64decode(frame), np.uint8)
    gray = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return None
    faces = _get_detector().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
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