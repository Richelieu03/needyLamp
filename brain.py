"""Module B: estimate whether one person is looking at the camera, locally.

Input: a base64 JPEG from camera.get_frame() (a data URL also works).
Output: is_looking(frame) -> bool. True means the person looks at the camera.

This is a geometric estimate, not a built-in gaze classifier. Adjust the
thresholds below using labeled photos from the actual webcam position.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from functools import lru_cache
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

import cv2
import numpy as np


# main.py checks this flag before importing the camera module.
MANUAL_MODE = False

# Starting values. Recalibrate with photos from the final camera position.
# Smaller head angles and narrower iris ranges make "yes" harder to trigger.
# Set this to False after calibration to hide the per-frame measurements.
DEBUG_GAZE = True
MAX_HEAD_YAW_DEG = 20.0
MAX_HEAD_PITCH_DEG = 18.0
MIN_IRIS_HORIZONTAL = 0.35
MAX_IRIS_HORIZONTAL = 0.65
MIN_IRIS_VERTICAL = 0.25
MAX_IRIS_VERTICAL = 0.75
MIN_EYE_OPEN_RATIO = 0.12

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
DEFAULT_MODEL_PATH = Path.home() / ".cache" / "needyLamp" / "face_landmarker.task"

# Approximate generic face coordinates, paired with MediaPipe landmarks below.
# Only the direction of the fitted face normal is used, not its distance.
_POSE_LANDMARK_IDS = (1, 152, 33, 263, 61, 291)
_POSE_MODEL_POINTS = np.array(
    [
        (0.0, 0.0, 0.0),       # nose tip
        (0.0, -330.0, -65.0), # chin
        (-225.0, 170.0, -135.0),
        (225.0, 170.0, -135.0),
        (-150.0, -150.0, -125.0),
        (150.0, -150.0, -125.0),
    ],
    dtype=np.float64,
)


class BrainError(Exception):
    """The local detector could not run or the supplied image was invalid."""


def _model_file(model_path: str | Path | None) -> Path:
    chosen = model_path or os.environ.get("FACE_LANDMARKER_MODEL")
    if chosen:
        path = Path(chosen).expanduser()
        if not path.is_file():
            raise BrainError(f"Face Landmarker model not found: {path}")
        return path

    path = DEFAULT_MODEL_PATH
    if path.is_file():
        return path

    # Download the public model once. Inference after that stays on this computer.
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Face Landmarker model once to {path} ...", flush=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary_path = Path(output.name)
            with urlopen(MODEL_URL, timeout=30) as response:
                shutil.copyfileobj(response, output)
        if temporary_path.stat().st_size < 1_000_000:
            raise BrainError("Downloaded Face Landmarker model is incomplete")
        temporary_path.replace(path)
    except (OSError, URLError, TimeoutError) as exc:
        raise BrainError(
            "Could not download the Face Landmarker model. Download it from "
            f"{MODEL_URL} and set FACE_LANDMARKER_MODEL to its local path."
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return path


@lru_cache(maxsize=2)
def _create_landmarker(path: str):
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise BrainError(
            "MediaPipe is not installed in this Python interpreter. "
            "Install it in PyCharm's interpreter with: python -m pip install mediapipe"
        ) from exc

    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=path),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=2,  # reject ambiguous images with multiple faces
    )
    try:
        return mp.tasks.vision.FaceLandmarker.create_from_options(options)
    except (RuntimeError, ValueError) as exc:
        raise BrainError(f"Could not load Face Landmarker model: {exc}") from exc


def _image_bytes(image_base64: str) -> bytes:
    if image_base64.startswith("data:"):
        header, separator, image_base64 = image_base64.partition(",")
        if not separator or ";base64" not in header:
            raise BrainError("Image data URL must contain base64 data")
    try:
        data = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BrainError("Image is not valid base64 data") from exc
    if not data:
        raise BrainError("Image data is empty")
    return data


def _eye_ratios(face, corner_a: int, corner_b: int, top: int, bottom: int, iris: int,
                width: int, height: int) -> tuple[float, float, float]:
    def point(index: int) -> np.ndarray:
        return np.array((face[index].x * width, face[index].y * height))

    start, end = point(corner_a), point(corner_b)
    upper, lower = point(top), point(bottom)
    pupil = point(iris)
    eye_axis = end - start
    lid_axis = lower - upper
    eye_width_sq = float(np.dot(eye_axis, eye_axis))
    eye_height_sq = float(np.dot(lid_axis, lid_axis))
    if eye_width_sq < 1.0 or eye_height_sq < 1.0:
        return math.nan, math.nan, 0.0
    horizontal = float(np.dot(pupil - start, eye_axis) / eye_width_sq)
    vertical = float(np.dot(pupil - upper, lid_axis) / eye_height_sq)
    openness = math.sqrt(eye_height_sq / eye_width_sq)
    return horizontal, vertical, openness


def _head_angles(face, width: int, height: int) -> tuple[float, float]:
    image_points = np.array(
        [(face[i].x * width, face[i].y * height) for i in _POSE_LANDMARK_IDS],
        dtype=np.float64,
    )
    focal_length = float(width)
    camera_matrix = np.array(
        ((focal_length, 0.0, width / 2),
         (0.0, focal_length, height / 2),
         (0.0, 0.0, 1.0)),
        dtype=np.float64,
    )
    try:
        ok, rotation_vector, _ = cv2.solvePnP(
            _POSE_MODEL_POINTS, image_points, camera_matrix,
            np.zeros((4, 1), dtype=np.float64), flags=cv2.SOLVEPNP_ITERATIVE,
        )
    except cv2.error:
        return math.nan, math.nan
    if not ok:
        return math.nan, math.nan
    rotation, _ = cv2.Rodrigues(rotation_vector)
    # The generic model's outward face normal points along negative model Z.
    normal = -rotation[:, 2]
    if normal[2] <= 0:
        return math.nan, math.nan
    yaw = math.degrees(math.atan2(normal[0], normal[2]))
    pitch = math.degrees(math.atan2(normal[1], normal[2]))
    return yaw, pitch


def _looks_at_camera(face, width: int, height: int) -> bool:
    if len(face) < 478:  # iris landmarks 468 and 473 are required
        if DEBUG_GAZE:
            print("Module B details: iris landmarks unavailable", flush=True)
        return False
    yaw, pitch = _head_angles(face, width, height)
    eyes = []
    for corners_and_iris in ((33, 133, 159, 145, 468), (362, 263, 386, 374, 473)):
        eyes.append(_eye_ratios(face, *corners_and_iris, width, height))

    head_ok = abs(yaw) <= MAX_HEAD_YAW_DEG and abs(pitch) <= MAX_HEAD_PITCH_DEG
    eyes_ok = all(
        MIN_IRIS_HORIZONTAL <= horizontal <= MAX_IRIS_HORIZONTAL
        and MIN_IRIS_VERTICAL <= vertical <= MAX_IRIS_VERTICAL
        and openness >= MIN_EYE_OPEN_RATIO
        for horizontal, vertical, openness in eyes
    )
    if DEBUG_GAZE:
        left, right = eyes
        reason = "yes" if head_ok and eyes_ok else (
            "head angle" if not head_ok else "eye position / blink"
        )
        print(
            f"Module B details: yaw={yaw:+.1f}°, pitch={pitch:+.1f}°; "
            f"left(h={left[0]:.2f}, v={left[1]:.2f}, open={left[2]:.2f}); "
            f"right(h={right[0]:.2f}, v={right[1]:.2f}, open={right[2]:.2f}); "
            f"decision={reason}",
            flush=True,
        )
    return head_ok and eyes_ok


def analyze_image(image_base64: str, *, model_path: str | Path | None = None) -> tuple[str, float]:
    """Return (yes/no, local processing time in seconds). No API call is made."""
    started = time.perf_counter()
    encoded = np.frombuffer(_image_bytes(image_base64), dtype=np.uint8)
    bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if bgr is None:
        raise BrainError("Could not decode image")

    try:
        import mediapipe as mp
    except ImportError as exc:
        raise BrainError(
            "MediaPipe is not installed in this Python interpreter. "
            "Install it in PyCharm's interpreter with: python -m pip install mediapipe"
        ) from exc
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    detector = _create_landmarker(str(_model_file(model_path)))
    try:
        result = detector.detect(image)
    except (RuntimeError, ValueError) as exc:
        raise BrainError(f"Face landmark detection failed: {exc}") from exc

    if len(result.face_landmarks) != 1:
        if DEBUG_GAZE:
            print(f"Module B details: faces={len(result.face_landmarks)}", flush=True)
        looking = False
    else:
        looking = _looks_at_camera(result.face_landmarks[0], image.width, image.height)
    return ("yes" if looking else "no"), time.perf_counter() - started


def is_looking(frame: str) -> bool:
    """Keep the A -> B -> C interface: base64 JPEG in, boolean out."""
    answer, elapsed = analyze_image(frame)
    print(f"Module B: {answer}, local processing {elapsed:.2f} seconds", flush=True)
    return answer == "yes"


def locate_face(image_base64: str, *, model_path: str | Path | None = None) -> tuple[float, float] | None:
    """Return the nose tip's normalized position (x, y), each in [0, 1],
    or None if there isn't exactly one face. Used for face tracking (e.g.
    swiveling the lamp head toward where the person is standing), separate
    from the yes/no gaze decision in analyze_image()/is_looking(). Runs its
    own local MediaPipe detection pass - cheap enough at the once-a-second
    rate this is called at, and keeps this independent of the carefully
    tuned gaze-detection logic above."""
    encoded = np.frombuffer(_image_bytes(image_base64), dtype=np.uint8)
    bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if bgr is None:
        raise BrainError("Could not decode image")

    try:
        import mediapipe as mp
    except ImportError as exc:
        raise BrainError(
            "MediaPipe is not installed in this Python interpreter. "
            "Install it in PyCharm's interpreter with: python -m pip install mediapipe"
        ) from exc
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    detector = _create_landmarker(str(_model_file(model_path)))
    try:
        result = detector.detect(image)
    except (RuntimeError, ValueError) as exc:
        raise BrainError(f"Face landmark detection failed: {exc}") from exc

    if len(result.face_landmarks) != 1:
        return None
    nose_tip = result.face_landmarks[0][1]   # landmark 1 = nose tip, same point used in _POSE_LANDMARK_IDS
    return nose_tip.x, nose_tip.y


def analyze_file(path: Path, *, model_path: str | Path | None = None) -> tuple[str, float]:
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise BrainError(f"Unsupported image format: {path}")
    frame = base64.b64encode(path.read_bytes()).decode("ascii")
    return analyze_image(frame, model_path=model_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate whether a person looks at the camera")
    parser.add_argument("image", nargs="?", type=Path, help="One JPG, PNG, or WebP image")
    parser.add_argument("--test-dir", type=Path, help="Directory containing yes/ and no/ subdirectories")
    parser.add_argument("--model", type=Path, help="Local face_landmarker.task file (optional)")
    args = parser.parse_args()
    if (args.image is None) == (args.test_dir is None):
        parser.error("Provide one image or use --test-dir")

    if args.image is not None:
        try:
            answer, elapsed = analyze_file(args.image, model_path=args.model)
        except (BrainError, OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"{answer}  local processing {elapsed:.2f} seconds")
        return 0

    images = [
        (path, expected)
        for expected in ("yes", "no")
        for path in sorted((args.test_dir / expected).glob("*"))
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    if not images:
        print("No test images found. Put them in yes/ and no/ subdirectories.", file=sys.stderr)
        return 1

    correct = 0
    errors = 0
    total_time = 0.0
    for path, expected in images:
        try:
            answer, elapsed = analyze_file(path, model_path=args.model)
        except (BrainError, OSError, ValueError) as exc:
            errors += 1
            print(f"{path}: error: {exc}")
            continue
        correct += answer == expected
        total_time += elapsed
        print(f"{path}: expected={expected} predicted={answer} time={elapsed:.2f}s")
    print(f"Accuracy: {correct}/{len(images)} = {correct / len(images):.1%}")
    print(f"Failed images: {errors}; average time: {total_time / (len(images) - errors):.2f}s" if len(images) > errors else f"Failed images: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
