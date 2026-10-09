import threading, time
import camera   # A: camera.get_frame() -> str（base64 的 JPEG）
import brain    # B: brain.is_looking(frame: str) -> bool
import lamp     # C: lamp.set_light(on: bool)；lamp.run() 跑 pygame 主循环

def worker():
    streak = 0
    while True:
        frame = camera.get_frame()
        looking = brain.is_looking(frame)
        streak = streak + 1 if looking else 0
        lamp.set_light(streak >= 2)   # 连续 2 次看着才亮
        time.sleep(1)

threading.Thread(target=worker, daemon=True).start()
lamp.run()   # pygame 必须在主线程
