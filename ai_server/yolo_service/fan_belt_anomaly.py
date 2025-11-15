"""
Fan/Belt 이상 탐지 (Optical Flow 기반)
- 전달된 frame sequence 기반으로 motion magnitude 분석
"""

import cv2
import numpy as np
from loguru import logger

# 임계값들
STOP_THRESH = 0.15
ACCEL_RATIO = 1.2
DECEL_RATIO = 0.90
VIB_STD_THR = 0.05
STABLE_TOL = 0.15


def estimate_motion(prev_gray, gray):
    """두 프레임 간 Optical Flow magnitude 계산"""
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15,
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0
    )
    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return mag


def classify_state(cur_mag, avg_mag, ratio, delta, std_motion):
    delta_norm = delta / (avg_mag + 1e-5)

    if cur_mag < STOP_THRESH:
        return "E_BELT_STOP"

    if ratio > 1.8 and std_motion > VIB_STD_THR:
        return "E_BELT_VIBRATION"

    if ratio > ACCEL_RATIO and delta_norm > STABLE_TOL:
        return "E_BELT_ACCELERATE"

    if ratio < DECEL_RATIO and delta_norm < -STABLE_TOL and abs(delta) > 1.0:
        return "E_BELT_SLOWDOWN"

    return "E_NORMAL"


async def analyze_fan_belt(frames, sharpest_frame=None, best_score=None, module_boxes=None):
    """
    Optical Flow 기반 fan/belt 이상 탐지
    * run_anomaly_detection()에서 frames 그대로 전달됨
    * sharpest_frame, module_boxes는 사용하지 않음 (인터페이스 맞추기 위함)
    """
    try:
        if len(frames) < 5:
            return {
                "type": "fan_belt",
                "status": "unknown",
                "message": "프레임 부족 (최소 3장 필요)"
            }

        logger.info(f"[fan_belt] 입력 프레임 수: {len(frames)}")
        return await _analyze_motion(frames)

    except Exception as e:
        logger.exception(f"[fan_belt] 분석 오류: {e}")
        return {
            "type": "fan_belt",
            "status": "error",
            "message": str(e)
        }


async def _analyze_motion(frames):
    gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]

    motion_mags = []
    for i in range(1, len(gray_frames)):
        mag = estimate_motion(gray_frames[i - 1], gray_frames[i])
        motion_mags.append(mag.mean())

    if len(motion_mags) < 3:
        return {"type": "fan_belt", "status": "unknown", "message": "프레임 부족"}

    avg_mag = float(np.mean(motion_mags))
    std_mag = float(np.std(motion_mags))
    cur_mag = float(motion_mags[-1])

    ratio = cur_mag / (avg_mag + 1e-5)
    delta = cur_mag - avg_mag

    state = classify_state(cur_mag, avg_mag, ratio, delta, std_mag)
    has_anomaly = (state != "E_NORMAL")

    return {
        "type": "fan_belt",
        "status": "anomaly" if has_anomaly else "normal",
        "message": f"상태: {state}",
        "state": state,
        "motion_magnitude": cur_mag,
        "avg_magnitude": avg_mag
    }
