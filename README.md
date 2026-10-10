# needyLamp

A desk lamp that only stays lit while you're actually looking at it. Look away for a
couple of seconds and it dims; look back and it lights back up, perking its head and
swiveling to track where your face is. Walk off entirely and, left alone long enough,
it starts to doze off.

It's a small local pipeline: a webcam frame goes in, a yes/no "are they looking at me"
decision and a face position come out, and a pygame-animated lamp reacts to both — all
running on your machine, no cloud API calls.

## How it works

```
camera.py ──► brain.py ──► main.py ──► lamp.py ──► lamp_skins.py
   │             │                         │             │
   │             └─► face_tracker.py ──────┘        lamp_behavior.py
   │
  webcam frame (base64 JPEG)
```

- **`camera.py`** — grabs a frame from the webcam, resizes it, and returns it as a
  base64 JPEG string. Handles camera permission failures gracefully (prints a message
  and exits instead of crashing) and releases the camera while the window is minimized.
- **`brain.py`** — decides whether the person in the frame is looking at the camera.
  Runs entirely locally with MediaPipe's Face Landmarker: estimates head pose (yaw/pitch)
  via `cv2.solvePnP` and checks iris position within the eyes to catch blinks/looking away.
  No network calls after the landmarker model is downloaded once.
- **`face_tracker.py`** — a lighter, separate pass that just finds *where* the face is in
  frame (not whether they're looking), using OpenCV's Haar cascade detector. Feeds the
  lamp's head-tracking, independent of `brain.py`'s yes/no decision.
- **`lamp.py`** — owns the lamp's state (on/off target, face focus, minimized) and the
  pygame main loop. Knows nothing about how the lamp is drawn.
- **`lamp_skins.py`** — everything about how the lamp *looks*. The default skin,
  `GooseneckLamp`, is a hand-drawn animated desk lamp with a springy neck, a light cone,
  and a bulb that glows warmer as it comes on.
- **`lamp_behavior.py`** — the lamp's *personality*, separate from its appearance: looking
  around and peeking while idle, dozing off after a while unattended, a happy little hop
  when it turns on.
- **`main.py`** — wires it all together. A background thread loops once a second:
  grab a frame → ask `brain` if they're looking → ask `face_tracker` where the face is →
  update the lamp. The main thread runs the pygame window (pygame needs the main thread).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` lists `mediapipe` and `pygame`; `opencv-python` comes along as a
MediaPipe dependency. The first run downloads two small model files once and caches
them under `~/.cache/needyLamp/`:
- the MediaPipe Face Landmarker model (for `brain.py`)
- a Haar cascade face detector (for `face_tracker.py` — OpenCV 5.0 stopped bundling
  these in its PyPI wheels, so this is fetched separately)

## Running it

```bash
python main.py
```

A window opens showing the lamp. Look at your webcam and, after a couple of frames in a
row confirming it, the lamp turns on and its head turns to track your face. Look away or
step out of frame and it dims and eventually settles into idle behavior.

Minimizing the window pauses everything (releases the camera, stops calling the model)
until you restore it.

### Standalone tests (no camera needed for some)

Each module can be run and tested on its own without the rest of the pipeline:

```bash
python test_camera.py --n 5        # take 5 photos, saved to out/, to sanity-check the camera
python brain.py some_photo.jpg     # yes/no + timing for a single image
python brain.py --test-dir labeled_photos/   # accuracy over yes/ and no/ subfolders
python face_tracker.py             # prints the detected face position once a second
python lamp.py                     # opens just the lamp window; your mouse stands in
                                    # for a face, so you can test the head-tracking
                                    # and on/off animations without a camera at all
```

### Manual mode (work in progress)

`main.py` and `lamp.py` already have the wiring for a manual mode — set
`brain.MANUAL_MODE = True` to skip the camera/model pipeline and drive "looking" by
pressing `Y`/`N` in the lamp window instead. It's not finished yet: `main.py` expects a
`brain.submit_manual_key` function that doesn't exist in `brain.py` yet, so turning on
`MANUAL_MODE` currently crashes. Left here as a note for whoever picks it up.

## Project layout

```
main.py            glue: the worker loop that ties camera → brain → face_tracker → lamp
camera.py          webcam capture (A)
brain.py           local gaze detection via MediaPipe (B)
face_tracker.py    local face-position detection via OpenCV Haar cascade
lamp.py             lamp state + pygame main loop (C)
lamp_skins.py       how the lamp is drawn (skins; default is GooseneckLamp)
lamp_behavior.py    the lamp's idle personality
test_camera.py      standalone camera self-test
requirements.txt   mediapipe, pygame (pulls in opencv)
```
