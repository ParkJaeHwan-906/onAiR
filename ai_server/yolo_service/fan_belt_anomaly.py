import cv2
import numpy as np
from loguru import logger
from collections import deque, Counter

MAG_THRESH = 0.5
SMOOTH_WINDOW = 4
TREND_WINDOW = 10
ACCEL_RATIO = 1.3
DECEL_RATIO = 0.90
STABLE_TOL = 0.3
STATE_SMOOTH = 7
INIT_IGNORE = 8


def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15,
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0
    )
    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return mag


def classify_state(cur_mag, avg_mag, ratio, delta, prev_state, std_motion):
    delta_norm = delta / (avg_mag + 1e-5)

    # 감속
    if ratio > ACCEL_RATIO and delta_norm > STABLE_TOL:
        state = "E_FAN_SLOWDOWN"

    # 가속
    elif ratio < DECEL_RATIO and delta_norm < -STABLE_TOL and abs(delta) > 1.0:
        state = "E_FAN_ACCELERATE"

    else:
        state = "E_NORMAL"

    # 진동
    if ratio > 1.8 and std_motion > 0.05:
        return "E_FAN_VIBRATION"

    # 히스테리시스
    if prev_state == "E_FAN_SLOWDOWN" and ratio > 0.95:
        state = "E_FAN_SLOWDOWN"

    elif prev_state == "E_FAN_ACCELERATE" and ratio < 1.05:
        state = "E_FAN_ACCELERATE"

    elif prev_state == "E_FAN_VIBRATION" and std_motion > 0.04:
        state = "E_FAN_VIBRATION"

    return state


async def analyze_fan_belt(frames, fan_belt_boxes):
    try:
        if len(frames) < 10:
            return {
                "type": "fan_belt",
                "status": "error",
                "detail": "not_enough_frames",
                "message": "프레임 부족",
                "results": {}
            }

        gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        results = {}

        # YOLO 박스 하나만 고정 기준으로 사용
        box = fan_belt_boxes[0]
        x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]

        mag_buf = deque(maxlen=SMOOTH_WINDOW)
        trend_buf = deque(maxlen=TREND_WINDOW)
        hist = deque(maxlen=STATE_SMOOTH)

        prev_state = "E_NORMAL"
        state_seq = []
        mag_global = []

        for i in range(1, len(gray_frames)):
            prev_roi = gray_frames[i - 1][y1:y2, x1:x2]
            curr_roi = gray_frames[i][y1:y2, x1:x2]

            if prev_roi.size == 0 or curr_roi.size == 0:
                continue

            mag = estimate_motion(prev_roi, curr_roi)
            mag_valid = mag[mag > MAG_THRESH]
            mag_mean = np.mean(mag_valid) if mag_valid.size > 0 else 0

            mag_global.append(mag_mean)
            mag_buf.append(mag_mean)
            smooth_mag = np.mean(mag_buf)
            std_motion = np.std(mag_buf)

            trend_buf.append(smooth_mag)
            avg_mag = np.mean(trend_buf)

            ratio = smooth_mag / (avg_mag + 1e-5)
            delta = smooth_mag - avg_mag

            if i <= INIT_IGNORE:
                state = "E_NORMAL"
            else:
                raw = classify_state(smooth_mag, avg_mag, ratio, delta, prev_state, std_motion)
                hist.append(raw)
                state = Counter(hist).most_common(1)[0][0]

            prev_state = state
            state_seq.append(state)

        cnt = Counter(state_seq)
        total = max(len(state_seq), 1)

        normal = cnt.get("E_NORMAL", 0) / total * 100
        slow = cnt.get("E_FAN_SLOWDOWN", 0) / total * 100
        accel = cnt.get("E_FAN_ACCELERATE", 0) / total * 100
        vib = cnt.get("E_FAN_VIBRATION", 0) / total * 100

        dom = max(cnt, key=cnt.get)

        # vibration 보정
        if (normal <= 20 and abs(slow - accel) <= 20) or vib >= 25:
            dom = "E_FAN_VIBRATION"

        final_state = dom
        status = "anomaly" if final_state != "E_NORMAL" else "normal"

        return {
            "type": "fan_belt",
            "status": status,
            "result": final_state,
            "percent": {
                "normal": normal,
                "slow": slow,
                "accel": accel,
                "vibration": vib
            }
        }

    except Exception as e:
        logger.exception(f"[fan_belt] error: {e}")
        return {
            "type": "fan_belt",
            "status": "error",
            "detail": "exception",
            "message": str(e),
            "results": {}
        }
