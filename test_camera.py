"""A's standalone self-test: no dependency on brain / lamp.

    python test_camera.py            # take one shot
    python test_camera.py --n 5      # take 5 shots, one per second

Open the images in out/ afterward to check they look right.
"""
import argparse
import base64
import os
import time

import camera

OUT_DIR = "out"


def shoot(index):
    b64 = camera.get_frame()
    assert isinstance(b64, str), f"get_frame should return str, got {type(b64)}"

    raw = base64.b64decode(b64)
    assert raw[:2] == b"\xff\xd8" and raw[-2:] == b"\xff\xd9", "decoded data is not a complete JPEG"

    path = os.path.join(OUT_DIR, f"frame_{int(time.time())}_{index}.jpg")
    with open(path, "wb") as f:
        f.write(raw)

    h, w = camera.get_frame_bgr().shape[:2]
    print(f"[{index}] {path}  size {w}x{h}  JPEG {len(raw)} bytes  base64 {len(b64)} chars")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=1, help="number of shots")
    p.add_argument("--interval", type=float, default=1.0, help="seconds between shots")
    args = p.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    for i in range(args.n):
        if i:
            time.sleep(args.interval)
        shoot(i)
    print("OK")


if __name__ == "__main__":
    main()
