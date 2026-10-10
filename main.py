import threading, time
import brain    # B: brain.is_looking(frame: str) -> bool
import lamp     # C: lamp.set_light(on: bool); lamp.run() runs the pygame main loop

# A single missed frame (for example, a blink) should not switch the lamp.
ON_AFTER_YES = 2
OFF_AFTER_NO = 1

if not brain.MANUAL_MODE:
    import camera  # A: camera.get_frame() -> str (base64 JPEG)

def worker():
    streak = 0
    while True:
        if not brain.MANUAL_MODE and lamp.is_minimized():
            # Nobody can see the lamp while it's minimized: release the
            # camera (turns off the capture indicator, frees the device for
            # other apps) and skip calling the API until it's restored.
            camera.release()
            streak = 0
            lamp.set_face_position(None)   # recenter the head while minimized
            time.sleep(1)
            continue

        try:
            frame = camera.get_frame()
            looking = brain.is_looking(frame)
            face = brain.locate_face(frame)   # (x, y) normalized, or None
            lamp.set_face_position(face[0] if face else None)
        except Exception as e:
            print("brain error, treating as not looking:", e)
            looking = False
            lamp.set_face_position(None)
            time.sleep(3)             # back off a bit before retrying
        streak = streak + 1 if looking else 0
        lamp.set_light(streak >= 2)   # only turn on after looking for 2 consecutive checks
        time.sleep(1)
        
if brain.MANUAL_MODE:
    lamp.set_key_handler(brain.submit_manual_key)
    print("Click the lamp window, then press Y or N (no Enter needed).", flush=True)

threading.Thread(target=worker, daemon=True).start()
lamp.run()   # pygame must run on the main thread
