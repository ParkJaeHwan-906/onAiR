"""
Fan/Belt 이상 탐지 (Optical Flow 기반)
- 프레임 리스트를 기반으로 motion magnitude 계산
- 평균 대비 증가/감소/정지/진동을 분석해 fan/belt 상태 판단
"""

import cv2
import numpy as np
from loguru import logger


# -------------------------------
# 하이퍼파라미터
# -------------------------------
STOP_THRESH = 0.15       # 거의 정지로 판단
ACCEL_RATIO = 1.2        # 급가속
DECEL_RATIO = 0.90       # 급감속
VIB_STD_THR = 0.05       # 진동 판단 기준
STABLE_TOL = 0.15        # 안정성 판단 기준


# -------------------------------
# Optical Flow 계산
# -------------------------------
def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15,
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0
    )
    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return mag


# -------------------------------
# fan/belt 상태 분류
# -------------------------------
def classify_state(cur_mag, avg_mag, ratio, delta, std_motion):
    delta_norm = delta / (avg_mag + 1e-5)

    # 완전 정지
    if cur_mag < STOP_THRESH:
        return "E_BELT_STOP"

    # 큰 진동
    if ratio > 1.8 and std_motion > VIB_STD_THR:
        return "E_BELT_VIBRATION"

    # 가속
    if ratio > ACCEL_RATIO and delta_norm > STABLE_TOL:
        return "E_BELT_ACCELERATE"

    # 감속
    if ratio < DECEL_RATIO and delta_norm < -STABLE_TOL and abs(delta) > 1.0:
        return "E_BELT_SLOWDOWN"

    return "E_NORMAL"


# -------------------------------
# 메인 분석 함수
# -------------------------------
async def analyze_fan_belt(frames):
    """
    Optical Flow 기반 fan/belt 이상 탐지
    run_anomaly_detection()에서 frames = list[np.ndarray] 전달됨
    """
    try:
        if len(frames) < 3:
            return {
                "type": "fan_belt",
                "status": "unknown",
                "message": "프레임 부족 (최소 3장 필요)"
            }

        logger.info(f"[fan_belt] 입력 프레임 수: {len(frames)}")

        return await _analyze_motion(frames)

    except Exception as e:
        logger.exception(f"[fan_belt] 분석 중 오류: {e}")
        return {
            "type": "fan_belt",
            "status": "error",
            "message": str(e)
        }


# -------------------------------
# Optical Flow 기반 모션 분석
# -------------------------------
async def _analyze_motion(frames):
    # grayscale 변환
    gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]

    # frame-wise motion magnitude 계산
    motion_mags = []
    for i in range(1, len(gray_frames)):
        mag = estimate_motion(gray_frames[i - 1], gray_frames[i])
        motion_mags.append(mag.mean())

    if len(motion_mags) < 3:
        return {"type": "fan_belt", "status": "unknown", "message": "프레임 부족"}

    # 통계 기반 상태 분석
    avg_mag = float(np.mean(motion_mags))
    std_mag = float(np.std(motion_mags))
    cur_mag = float(motion_mags[-1])

    ratio = cur_mag / (avg_mag + 1e-5)
    delta = cur_mag - avg_mag

    state = classify_state(cur_mag, avg_mag, ratio, delta, std_mag)
    has_anomaly = state != "E_NORMAL"

    return {
        "type": "fan_belt",
        "status": "anomaly" if has_anomaly else "normal",
        "message": f"상태: {state}",
        "state": state,
        "motion_magnitude": cur_mag,
        "avg_magnitude": avg_mag
    }
