import threading, time
import brain    # B: brain.is_looking(frame: str) -> bool
import lamp     # C: lamp.set_light(on: bool); lamp.run() runs the pygame main loop

# A single missed frame (for example, a blink) should not switch the lamp.
ON_AFTER_YES = 2
OFF_AFTER_NO = 1
GAZE_CHECK_INTERVAL = 1.0
FACE_TRACK_INTERVAL = 0.15

if not brain.MANUAL_MODE:
    import camera        # A: camera.get_frame() -> str (base64 JPEG)
    import face_tracker   # find_face(frame) -> (x, y) in -1..1, or None

def worker():
    streak = 0
    next_gaze_check = 0.0
    while True:
        if not brain.MANUAL_MODE and lamp.is_minimized():
            # Release the camera while the window is minimized.
            camera.release()
            streak = 0
            next_gaze_check = 0.0
            lamp.set_focus(None)
            time.sleep(1)
            continue

        try:
            frame = camera.get_frame()
            lamp.set_focus(face_tracker.find_face(frame))
            # Face position updates more often while the light is on; gaze
            # detection still runs about once per second as before.
            if time.monotonic() >= next_gaze_check:
                looking = brain.is_looking(frame)
                streak = streak + 1 if looking else 0
                lamp.set_light(streak >= ON_AFTER_YES)
                next_gaze_check = time.monotonic() + GAZE_CHECK_INTERVAL
        except Exception as e:
            print("brain error, treating as not looking:", e)
            streak = 0
            next_gaze_check = 0.0
            lamp.set_light(False)
            lamp.set_focus(None)
            time.sleep(3)
            continue
        time.sleep(FACE_TRACK_INTERVAL if lamp.is_on() else GAZE_CHECK_INTERVAL)

if brain.MANUAL_MODE:
    lamp.set_key_handler(brain.submit_manual_key)
    print("Click the lamp window, then press Y or N (no Enter needed).", flush=True)

threading.Thread(target=worker, daemon=True).start()
lamp.run()   # pygame must run on the main thread
