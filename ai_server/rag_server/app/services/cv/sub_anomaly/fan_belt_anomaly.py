"""
Fan/Belt 이상 탐지 (Optical Flow + YOLO)
- 영상 대신 프레임 리스트 기반 (Redis 버퍼 입력)
- classify_state 기반으로 belt/fan의 상태 변화 감지
"""

import cv2
import numpy as np
from collections import deque, Counter
# from ultralytics import YOLO
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
        logger.warning("⚠️ [fan_belt] 테스트 모드: YOLO 기반 팬/벨트 탐지 생략")
        # model = YOLO(MODEL_PATH)

        # 이하 YOLO 기반 이상 탐지 로직은 테스트 모드에서 비활성화
        return {
            "type": "fan_belt",
            "status": "disabled",
            "message": "YOLO 기반 팬/벨트 분석이 테스트 모드로 비활성화되었습니다"
        }

    except Exception as e:
        logger.exception(f"[fan_belt] 분석 중 오류: {e}")
        return {"type": "fan_belt", "status": "error", "message": str(e)}
