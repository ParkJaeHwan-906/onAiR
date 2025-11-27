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
    # 정상
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

        if not fan_belt_boxes:
            return {
                "type": "fan_belt",
                "status": "error",
                "detail": "no_yolo_box",
                "message": "YOLO 박스 없음",
                "results": {}
            }

        # BGR -> Gray 변환
        gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        H, W = gray_frames[0].shape

        # YOLO 박스 하나만 사용 (고정 ROI)
        box = fan_belt_boxes[0]
        x1, y1, x2, y2 = int(box["x1"]), int(box["y1"]), int(box["x2"]), int(box["y2"])

        # 안전하게 클램프
        x1 = max(0, min(x1, W - 1))
        x2 = max(0, min(x2, W))
        y1 = max(0, min(y1, H - 1))
        y2 = max(0, min(y2, H))

        if x2 <= x1 or y2 <= y1:
            return {
                "type": "fan_belt",
                "status": "error",
                "detail": "invalid_roi",
                "message": "ROI 잘못된 좌표",
                "results": {}
            }

        mag_buf = deque(maxlen=SMOOTH_WINDOW)
        trend_buf = deque(maxlen=TREND_WINDOW)
        state_hist = deque(maxlen=STATE_SMOOTH)

        prev_state = "E_NORMAL"
        results = []
        mag_global = []

        prev_gray = gray_frames[0]
        frame_idx = 1

        for i in range(1, len(gray_frames)):
            gray = gray_frames[i]

            if frame_idx % 2 == 0:
                prev_roi = prev_gray[y1:y2, x1:x2]
                roi_gray = gray[y1:y2, x1:x2]

                if prev_roi.size == 0 or roi_gray.size == 0:
                    prev_gray = gray
                    frame_idx += 1
                    continue

                mag = estimate_motion(prev_roi, roi_gray)
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

                if frame_idx <= INIT_IGNORE:
                    state = "E_NORMAL"
                else:
                    raw = classify_state(smooth_mag, avg_mag, ratio, delta, prev_state, std_motion)
                    state_hist.append(raw)
                    state = Counter(state_hist).most_common(1)[0][0]

                logger.info(
                    f"[fan_belt][frame={frame_idx:04d}] "
                    f"mag={smooth_mag:.3f}, ratio={ratio:.2f}, std={std_motion:.3f} → {state}"
                )

                    
                prev_state = state
                results.append(state)

            prev_gray = gray
            frame_idx += 1

        cnt = Counter(results)
        total = max(len(results), 1)

        normal = cnt.get("E_NORMAL", 0) / total * 100
        slow = cnt.get("E_FAN_SLOWDOWN", 0) / total * 100
        accel = cnt.get("E_FAN_ACCELERATE", 0) / total * 100
        vib = cnt.get("E_FAN_VIBRATION", 0) / total * 100

        dom = max(cnt, key=cnt.get)

        if (normal <= 20 and abs(slow - accel) <= 20) or vib >= 25:
            dom = "E_FAN_VIBRATION"

        final_state = dom
        status = "anomaly" if final_state != "E_NORMAL" else "normal"
        
        # detail 필드 추가 (다른 모듈과 일관성 유지)
        detail = final_state if status == "anomaly" else "normal"
        
        # 메시지 생성
        message_map = {
            "E_NORMAL": "팬 벨트가 정상 상태입니다",
            "E_FAN_SLOWDOWN": "팬 벨트가 감속 중입니다",
            "E_FAN_ACCELERATE": "팬 벨트가 가속 중입니다",
            "E_FAN_VIBRATION": "팬 벨트에 진동이 감지되었습니다"
        }
        message = message_map.get(final_state, f"팬 벨트 상태: {final_state}")

        return {
            "type": "fan_belt",
            "status": status,
            "detail": detail,  # ✅ detail 필드 추가 (다른 모듈과 일관성)
            "result": final_state,  # 하위 호환성을 위해 유지
            "message": message,  # ✅ message 필드 추가
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
