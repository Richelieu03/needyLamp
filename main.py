import threading, time
import brain    # B: brain.is_looking(frame: str) -> bool
import lamp     # C: lamp.set_light(on: bool); lamp.run() runs the pygame main loop
import servo_head   # servo: drives the physical lamp head over USB serial

# Turn on quickly, turn off slowly: a blink or a quick glance away
# should not switch the lamp off.
ON_AFTER_YES = 2     # consecutive "looking" checks before the lamp turns on
OFF_AFTER_NO = 3     # consecutive "not looking" checks before it turns off (~3 s)
GAZE_CHECK_INTERVAL = 1.0
FACE_TRACK_INTERVAL = 0.15

if not brain.MANUAL_MODE:
    import camera        # A: camera.get_frame() -> str (base64 JPEG)

# servo: connect to the Arduino if it is plugged in; otherwise run without it
try:
    servo_head.connect()
    print("Servo connected.", flush=True)
except Exception as e:
    print("Servo not connected, running without it:", e, flush=True)


def update_light(looking, streaks):
    """Count consecutive yes/no answers and switch the lamp with hysteresis."""
    if looking:
        streaks["yes"] += 1
        streaks["no"] = 0
    else:
        streaks["no"] += 1
        streaks["yes"] = 0
    if streaks["yes"] >= ON_AFTER_YES:
        lamp.set_light(True)
        servo_head.set_light(True)    # physical LED follows the on-screen lamp
    elif streaks["no"] >= OFF_AFTER_NO:
        lamp.set_light(False)
        servo_head.set_light(False)
    # otherwise keep the current state


def worker():
    streaks = {"yes": 0, "no": 0}
    next_gaze_check = 0.0
    multi_seen = False
    while True:
        if not brain.MANUAL_MODE and lamp.is_minimized():
            # Release the camera while the window is minimized.
            camera.release()
            streaks = {"yes": 0, "no": 0}
            next_gaze_check = 0.0
            multi_seen = False
            lamp.set_focus(None)
            servo_head.look_at(None)     # servo: recenters after a short hold
            time.sleep(1)
            continue

        try:
            frame = camera.get_frame()
            face, face_count = brain.locate_face_and_count(frame)  # (x, y) or None; count capped at 2
            # Flip x so the lamp follows the person as seen on screen.
            lamp.set_focus((1.0 - 2.0 * face[0], 2.0 * face[1] - 1.0) if face else None)
            servo_head.look_at(face[0] if face else None)   # servo: smoothed, holds briefly if face is lost
            # Face position updates more often while the light is on; gaze
            # detection still runs about once per second as before.
            if face_count >= 2:
                # A group keeps the lamp on, regardless of anyone's gaze.
                # Reset both streaks so one missed detection cannot switch it off.
                if not multi_seen:
                    print("B module: multiple faces detected; lamp ON", flush=True)
                multi_seen = True
                lamp.set_light(True)
                servo_head.set_light(True)
                
                streaks = {"yes": 0, "no": 0}
                next_gaze_check = time.monotonic() + GAZE_CHECK_INTERVAL
            else:
                multi_seen = False
                if time.monotonic() >= next_gaze_check:
                    update_light(brain.is_looking(frame), streaks)
                    next_gaze_check = time.monotonic() + GAZE_CHECK_INTERVAL
        except Exception as e:
            print("brain error, treating as not looking:", e)
            update_light(False, streaks)   # repeated errors turn the lamp off, a single one doesn't
            next_gaze_check = 0.0
            lamp.set_focus(None)
            servo_head.look_at(None)
            time.sleep(3)
            continue
        time.sleep(FACE_TRACK_INTERVAL if lamp.is_on() else GAZE_CHECK_INTERVAL)

if brain.MANUAL_MODE:
    lamp.set_key_handler(brain.submit_manual_key)
    print("Click the lamp window, then press Y or N (no Enter needed).", flush=True)

threading.Thread(target=worker, daemon=True).start()
lamp.run()   # pygame must run on the main thread
