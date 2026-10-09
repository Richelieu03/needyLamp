import threading, time
import camera   # A: camera.get_frame() -> str (base64 JPEG)
import brain    # B: brain.is_looking(frame: str) -> bool
import lamp     # C: lamp.set_light(on: bool); lamp.run() runs the pygame main loop

def worker():
    streak = 0
    while True:
        frame = camera.get_frame()
        looking = brain.is_looking(frame)
        streak = streak + 1 if looking else 0
        lamp.set_light(streak >= 2)   # only turn on after looking for 2 consecutive checks
        time.sleep(1)

threading.Thread(target=worker, daemon=True).start()
lamp.run()   # pygame must run on the main thread
