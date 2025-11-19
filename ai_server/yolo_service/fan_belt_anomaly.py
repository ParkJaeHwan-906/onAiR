import cv2
import numpy as np
from loguru import logger
from collections import deque, Counter


# Hyperparameters
MAG_THRESH = 0.5
STOP_THRESH = 0.15
SMOOTH_WINDOW = 4
TREND_WINDOW = 10
ACCEL_RATIO = 1.2
DECEL_RATIO = 0.90
STABLE_TOL = 0.15
STATE_SMOOTH = 7
INIT_IGNORE = 5


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

    # 안정화된 상태 유지
    if prev_state == "E_BELT_ACCELERATE" and ratio > 0.95:
        state = "E_BELT_ACCELERATE"
    elif prev_state == "E_BELT_SLOWDOWN" and ratio < 1.05:
        state = "E_BELT_SLOWDOWN"
    elif prev_state == "E_BELT_VIBRATION" and std_motion > 0.04:
        state = "E_BELT_VIBRATION"

    return state


# -----------------------------
# RAG-friendly 메시지 매핑
# -----------------------------
RAG_MAP = {
    "E_NORMAL": ("normal", "벨트는 정상적으로 동작하고 있습니다."),
    "E_BELT_STOP": ("belt_stop", "벨트가 멈춰 있는 것으로 감지되었습니다."),
    "E_BELT_ACCELERATE": ("belt_accelerate", "벨트가 비정상적으로 빠르게 가속되고 있습니다."),
    "E_BELT_SLOWDOWN": ("belt_slowdown", "벨트가 비정상적으로 감속되고 있습니다."),
    "E_BELT_VIBRATION": ("belt_vibration", "벨트에서 이상 진동이 감지되었습니다.")
}


# -----------------------------
# MAIN ENTRY (NEW STRUCTURE)
# -----------------------------
async def analyze_fan_belt(frames, belt_boxes):
    try:
        if len(frames) < 5:
            return {
                "type": "fan_belt",
                "status": "error",
                "detail": "not_enough_frames",
                "message": "프레임이 충분하지 않아 분석할 수 없습니다.",
                "results": {}
            }

        if not belt_boxes:
            return {
                "type": "fan_belt",
                "status": "not_found",
                "detail": "no_belt_detected",
                "message": "벨트가 탐지되지 않았습니다.",
                "results": {}
            }

        gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        results = {}

        # 각 벨트 박스마다 분석
        for idx, box in enumerate(belt_boxes):
            x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]

            mag_buf = deque(maxlen=SMOOTH_WINDOW)
            trend_buf = deque(maxlen=TREND_WINDOW)
            hist = deque(maxlen=STATE_SMOOTH)
            prev_state = "E_NORMAL"
            state_seq = []

            for i in range(1, len(gray_frames)):
                prev_roi = gray_frames[i - 1][y1:y2, x1:x2]
                curr_roi = gray_frames[i][y1:y2, x1:x2]

                if prev_roi.size == 0 or curr_roi.size == 0:
                    continue

                mag = estimate_motion(prev_roi, curr_roi)
                mag_valid = mag[mag > MAG_THRESH]
                mag_mean = np.mean(mag_valid) if mag_valid.size > 0 else 0

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
            dominant = cnt.most_common(1)[0][0]

            results[f"belt_{idx}"] = {
                "dominant": dominant,
                "states": dict(cnt)
            }

        # 최종 dominant 상태 선택 (하나라도 anomaly면 anomaly)
        dominants = [belt["dominant"] for belt in results.values()]
        final_state = "E_NORMAL"
        for s in dominants:
            if s != "E_NORMAL":
                final_state = s
                break

        detail, message = RAG_MAP.get(final_state, ("unknown", "알 수 없는 상태입니다."))
        status = "anomaly" if final_state != "E_NORMAL" else "normal"

        return {
            "type": "fan_belt",
            "status": status,
            "detail": detail,
            "message": message,
            "results": results
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
