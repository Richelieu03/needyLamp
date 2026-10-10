"""A's responsibility: camera module.

Contract (see main.py):
    camera.get_frame() -> str   # base64-encoded JPEG (no "data:" prefix)
"""
import atexit
import base64
import sys
import threading

import cv2

WIDTH = 512        # resize to this width to save bandwidth/tokens
QUALITY = 70        # JPEG quality

_cap = None
_lock = threading.Lock()


def _request_camera_access():
    """Try to open the camera once. On macOS this is also what triggers the
    OS camera-permission prompt on first use, so "requesting access" and
    "opening the camera" are the same call here. If access was not granted
    (or there is no camera), exit cleanly with a friendly message instead of
    raising an exception: in main.py's daemon worker thread, SystemExit is
    swallowed silently by `threading` (no scary traceback), and in a plain
    script it just prints our message and exits."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap.release()
        print(
            "Camera unavailable: camera access was not granted (or no "
            "camera was found). On macOS, check System Settings > Privacy "
            "& Security > Camera, allow access for this app, then run "
            "again.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return cap


def _get_cap():
    """Lazily open the camera singleton. Reopening it every second is
    expensive and prone to failure."""
    global _cap
    with _lock:
        if _cap is None or not _cap.isOpened():
            _cap = _request_camera_access()
        return _cap


def get_frame_bgr():
    """Grab one raw frame (OpenCV BGR numpy array), already resized to WIDTH."""
    cap = _get_cap()
    ok, frame = cap.read()
    if not ok:
        ok, frame = cap.read()   # the very first frame after opening is often empty, retry once
    if not ok:
        raise RuntimeError("Failed to read from the camera")

    h, w = frame.shape[:2]
    if w > WIDTH:
        new_h = round(h * WIDTH / w)
        frame = cv2.resize(frame, (WIDTH, new_h), interpolation=cv2.INTER_AREA)
    return frame


def get_frame() -> str:
    """Grab one frame and return it as a base64-encoded JPEG string."""
    frame = get_frame_bgr()
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, QUALITY])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def release():
    """Close the camera so the capture indicator light doesn't stay on after exit."""
    global _cap
    with _lock:
        if _cap is not None:
            _cap.release()
            _cap = None


atexit.register(release)
