import cv2
import numpy as np
from collections import deque, Counter
from ultralytics import YOLO
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "../../../models/module_best.pt")

RESIZE = (640, 480)
STOP_THRESH = 0.15
ACCEL_RATIO = 1.2
DECEL_RATIO = 0.9
STATE_SMOOTH = 5
INIT_IGNORE = 5

def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15, iterations=3,
        poly_n=5, poly_sigma=1.2, flags=0)
    mag, _ = cv2.cartToPolar(flow[...,0], flow[...,1])
    return mag

async def analyze_fan_belt(frames):
    """버퍼 전체 기반 팬/벨트 이상 탐지"""
    if len(frames) < 3:
        return {"type": "fan_belt", "status": "unknown", "message": "프레임 부족"}

    model = YOLO(MODEL_PATH)
    prev_gray = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    belts = {}

    for i in range(1, len(frames)):
        gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        mag = estimate_motion(prev_gray, gray)
        prev_gray = gray

        results = await model.predict(frames[i], conf=0.5, device="cpu", verbose=False)
        for box in results[0].boxes:
            cls = model.names[int(box.cls)]
            if "belt" not in cls.lower() and "fan" not in cls.lower():
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            roi = mag[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            mag_mean = np.mean(roi)
            bid = f"{cls}_{i}"
            if bid not in belts:
                belts[bid] = deque(maxlen=STATE_SMOOTH)
            if mag_mean < STOP_THRESH:
                state = "E_BELT_STOP"
            elif mag_mean > 0.8:
                state = "E_BELT_ACCEL"
            else:
                state = "E_NORMAL"
            belts[bid].append(state)

    if not belts:
        return {"type": "fan_belt", "status": "not_found", "message": "팬/벨트 미검출"}

    summary = {}
    for bid, states in belts.items():
        cnt = Counter(states)
        dom = max(cnt, key=cnt.get)
        summary[bid] = {"dominant": dom, "hist": dict(cnt)}

    return {"type": "fan_belt", "status": "done", "results": summary}
