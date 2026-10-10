import threading, time
import brain    # B: brain.is_looking(frame: str) -> bool
import lamp     # C: lamp.set_light(on: bool); lamp.run() runs the pygame main loop

# A single missed frame (for example, a blink) should not switch the lamp.
ON_AFTER_YES = 2
OFF_AFTER_NO = 1

if not brain.MANUAL_MODE:
    import camera  # A: camera.get_frame() -> str (base64 JPEG)

def worker():
    looking_streak = 0
    away_streak = 0
    lamp.set_light(False)
    while True:
        frame = "" if brain.MANUAL_MODE else camera.get_frame()
        looking = brain.is_looking(frame)
        looking_streak = looking_streak + 1 if looking else 0
        away_streak = away_streak + 1  if not looking else 0
        if looking_streak >= ON_AFTER_YES and not lamp.is_on():
            lamp.set_light(True)
        elif away_streak >= OFF_AFTER_NO and lamp.is_on():
            lamp.set_light(False)
        time.sleep(1)

if brain.MANUAL_MODE:
    lamp.set_key_handler(brain.submit_manual_key)
    print("Click the lamp window, then press Y or N (no Enter needed).", flush=True)

threading.Thread(target=worker, daemon=True).start()
lamp.run()   # pygame must run on the main thread
