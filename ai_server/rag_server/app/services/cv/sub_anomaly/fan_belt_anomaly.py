"""
Fan/Belt 이상 탐지 (Optical Flow + YOLO)
- 영상 대신 프레임 리스트 기반 (Redis 버퍼 입력)
- classify_state 기반으로 belt/fan의 상태 변화 감지
"""

import cv2
import numpy as np
from collections import deque, Counter
from ultralytics import YOLO
import asyncio
from loguru import logger
import os

# -------------------------------
# 기본 파라미터
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "../../../models/module_best.pt")

MAG_THRESH = 0.5
STOP_THRESH = 0.15
SMOOTH_WINDOW = 4
TREND_WINDOW = 10
ACCEL_RATIO = 1.2
DECEL_RATIO = 0.90
STABLE_TOL = 0.15
STATE_SMOOTH = 7
INIT_IGNORE = 5


# -------------------------------
# Optical Flow 계산
# -------------------------------
def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15, iterations=3,
        poly_n=5, poly_sigma=1.2, flags=0
    )
    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return mag


# -------------------------------
# 상태 분류
# -------------------------------
def classify_state(cur_mag, avg_mag, ratio, delta, prev_state, std_motion):
    delta_norm = delta / (avg_mag + 1e-5)

    if cur_mag < STOP_THRESH:
        return "E_BELT_STOP"

    if ratio > 1.8 and std_motion > 0.05:
        return "E_BELT_VIBRATION"

    if ratio > ACCEL_RATIO and delta_norm > STABLE_TOL:
        state = "E_BELT_ACCELERATE"
    elif ratio < DECEL_RATIO and delta_norm < -STABLE_TOL and abs(delta) > 1.0:
        state = "E_BELT_SLOWDOWN"
    else:
        state = "E_NORMAL"

    # 히스테리시스
    if prev_state == "E_BELT_ACCELERATE" and ratio > 0.95:
        state = "E_BELT_ACCELERATE"
    elif prev_state == "E_BELT_SLOWDOWN" and ratio < 1.05:
        state = "E_BELT_SLOWDOWN"
    elif prev_state == "E_BELT_VIBRATION" and std_motion > 0.04:
        state = "E_BELT_VIBRATION"

    return state


# -------------------------------
# 메인 분석 (프레임 리스트 기반)
# -------------------------------
async def analyze_fan_belt(frames):
    """버퍼 전체 기반 팬/벨트 이상 탐지"""
    try:
        if len(frames) < 3:
            return {
                "type": "fan_belt",
                "status": "unknown",
                "message": "프레임 부족 (최소 3장 필요)"
            }

        logger.info(f"[fan_belt] 입력 프레임 수: {len(frames)}")
        model = YOLO(MODEL_PATH)

        prev_gray = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
        belts = {}
        frame_idx = 1

        for i in range(1, len(frames)):
            gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            mag = estimate_motion(prev_gray, gray)
            prev_gray = gray

            # YOLO 탐지 (belt/fan)
            results = await asyncio.to_thread(model.predict, frames[i], conf=0.45, verbose=False)
            belt_boxes = []
            for r in results:
                for box in r.boxes:
                    cls = model.names[int(box.cls)]
                    if "belt" in cls.lower() or "fan" in cls.lower():
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        belt_boxes.append((cls, (x1, y1, x2, y2)))

            if not belt_boxes:
                frame_idx += 1
                continue

            for (cls, (x1, y1, x2, y2)) in belt_boxes:
                roi_prev = prev_gray[y1:y2, x1:x2]
                roi_gray = gray[y1:y2, x1:x2]
                if roi_prev.size == 0 or roi_gray.size == 0:
                    continue

                mag_roi = mag[y1:y2, x1:x2]
                mag_valid = mag_roi[mag_roi > MAG_THRESH]
                mag_mean = np.mean(mag_valid) if mag_valid.size > 0 else 0

                bid = f"{cls}_{i}"
                if bid not in belts:
                    belts[bid] = {
                        "mag_buf": deque(maxlen=SMOOTH_WINDOW),
                        "trend_buf": deque(maxlen=TREND_WINDOW),
                        "state_hist": deque(maxlen=STATE_SMOOTH),
                        "prev_state": "E_NORMAL",
                        "results": []
                    }

                b = belts[bid]
                b["mag_buf"].append(mag_mean)
                smooth_mag = np.mean(b["mag_buf"])
                std_motion = np.std(b["mag_buf"])
                b["trend_buf"].append(smooth_mag)
                avg_mag = np.mean(b["trend_buf"])
                ratio = smooth_mag / (avg_mag + 1e-5)
                delta = smooth_mag - avg_mag

                if frame_idx <= INIT_IGNORE:
                    state = "E_NORMAL"
                else:
                    raw = classify_state(smooth_mag, avg_mag, ratio, delta, b["prev_state"], std_motion)
                    b["state_hist"].append(raw)
                    state = max(Counter(b["state_hist"]), key=lambda k: Counter(b["state_hist"])[k])

                b["prev_state"] = state
                b["results"].append(state)
            frame_idx += 1

        if not belts:
            return {"type": "fan_belt", "status": "not_found", "message": "팬/벨트 미검출"}

        # -------------------------------
        # 상태 요약
        # -------------------------------
        summary = {}
        for bid, b in belts.items():
            cnt = Counter(b["results"])
            total = max(len(b["results"]), 1)
            n, s, a, v, st = [cnt.get(k, 0)/total*100 for k in
                              ["E_NORMAL", "E_BELT_SLOWDOWN", "E_BELT_ACCELERATE", "E_BELT_VIBRATION", "E_BELT_STOP"]]
            dom = max(cnt, key=cnt.get)
            if (n <= 20 and abs(s - a) <= 20) or v >= 25:
                dom = "E_BELT_VIBRATION"
            summary[bid] = dict(normal=n, slow=s, accel=a, vib=v, stop=st, result=dom)

        logger.info(f"[fan_belt] 결과 요약: {summary}")
        return {"type": "fan_belt", "status": "done", "results": summary}

    except Exception as e:
        logger.exception(f"[fan_belt] 분석 중 오류: {e}")
        return {"type": "fan_belt", "status": "error", "message": str(e)}
