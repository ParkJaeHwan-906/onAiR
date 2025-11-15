"""
게이지 이상 탐지 (local YOLO + Sharpness)
- 가장 선명한 frame 1장 선택
- module_best.pt 모델로 gauge/thermometer/pressure 영역 추출
- ROI 기반 지침 각도 계산 → 값 변환 → 이상 판단
"""

import os
import cv2
import numpy as np
from pathlib import Path
from loguru import logger
from ultralytics import YOLO


# ------------------------------
# 모델 경로
# ------------------------------

YOLO_MODEL_PATH = "/app/ai_server/yolo_service/models/device_best.pt"

# ------------------------------
# 하이퍼파라미터
# ------------------------------
MIN_SHARPNESS = 70.0

_module_model = None   # lazy-loaded YOLO


# ------------------------------
# 유틸 함수들
# ------------------------------
def calc_sharpness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def detect_gauge_value_fast(img: np.ndarray):
    """Hough 기반 게이지 바늘 각도 추출 (rough)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        1,
        200,
        param1=100,
        param2=22,
        minRadius=50,
        maxRadius=0,
    )
    if circles is None:
        return None

    x0, y0, R = np.uint16(np.around(circles[0][0]))
    edges = cv2.Canny(blur, 50, 150)
    h, w = gray.shape

    thetas = np.deg2rad(np.arange(0, 360, 2))
    scores = []

    for th in thetas:
        xs = (x0 + np.cos(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
        ys = (y0 - np.sin(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)
        scores.append(edges[ys, xs].sum())

    if not scores:
        return None

    angle = np.rad2deg(thetas[np.argmax(scores)]) % 360
    return angle


def judge_abnormal(gauge_type: str, value: float):
    """온도 / 압력 기준 이상 판단"""

    if "thermometer" in gauge_type.lower():
        if value > 80:
            return "온도 과열", "high"
        if value < 5:
            return "온도 너무 낮음", "low"
        return "정상", "normal"

    if "pressure" in gauge_type.lower():
        if value > 1.5:
            return "압력 과다", "high"
        if value < 0.2:
            return "압력 부족", "low"
        return "정상", "normal"

    return "Unknown type", "unknown"


# ------------------------------
# 모델 초기화
# ------------------------------
def _load_model_once():
    global _module_model
    if _module_model is None:
        _module_model = YOLO(str(MODULE_MODEL_PATH))
        _module_model.fuse()
        logger.info("📦 gauge_anomaly: Module YOLO 로드 완료")


# ------------------------------
# 메인 함수
# ------------------------------
async def analyze_gauge(frames):
    """
    게이지 이상 탐지 (단일 프레임 기준)
    run_anomaly_detection()에서 frames = list[np.ndarray] 전달됨
    """
    try:
        if not frames:
            return {
                "type": "gauge",
                "status": "unknown",
                "message": "입력 프레임 없음"
            }

        # ------------------------------
        # 1. sharpest frame 선택
        # ------------------------------
        sharp_list = [(f, calc_sharpness(f)) for f in frames]
        sharp_list = [(f, s) for f, s in sharp_list if s > MIN_SHARPNESS]

        if not sharp_list:
            return {
                "type": "gauge",
                "status": "low_confidence",
                "message": "모든 프레임이 흐림"
            }

        sharpest_frame, best_score = max(sharp_list, key=lambda x: x[1])

        # ------------------------------
        # 2. YOLO 모델 로드
        # ------------------------------
        _load_model_once()

        # ------------------------------
        # 3. YOLO로 gauge/thermometer/pressure ROI 추출
        # ------------------------------
        yolo_results = _module_model.predict(sharpest_frame, conf=0.5, verbose=False)

        detections = []
        for r in yolo_results:
            for box in r.boxes:
                label = _module_model.names[int(box.cls)]
                if any(k in label.lower() for k in ["gauge", "thermometer", "pressure"]):
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    roi = sharpest_frame[y1:y2, x1:x2]
                    if roi.size > 0:
                        detections.append({"type": label, "roi": roi})

        if not detections:
            return {
                "type": "gauge",
                "status": "not_found",
                "sharpness": best_score,
                "message": "게이지 미검출",
                "results": {}
            }

        # ------------------------------
        # 4. ROI 기반 값 분석
        # ------------------------------
        final_results = {}
        found_anomaly = False

        for det in detections:
            gauge_type = det["type"]
            roi = det["roi"]

            angle = detect_gauge_value_fast(roi)
            if angle is None:
                continue

            # 값으로 변환
            if "thermometer" in gauge_type.lower():
                value = (angle / 360.0) * 100    # 0–100도
            elif "pressure" in gauge_type.lower():
                value = (angle / 360.0) * 2.0    # 0–2.0 bar
            else:
                value = angle / 360.0

            msg, status = judge_abnormal(gauge_type, value)

            final_results[gauge_type] = {
                "value": float(value),
                "angle": float(angle),
                "status": status,
                "message": msg
            }

            if status != "normal":
                found_anomaly = True

        return {
            "type": "gauge",
            "status": "anomaly" if found_anomaly else "normal",
            "sharpness": best_score,
            "results": final_results,
            "message": "이상 탐지됨" if found_anomaly else "정상"
        }

    except Exception as e:
        logger.exception(f"[gauge] 분석 중 오류: {e}")
        return {
            "type": "gauge",
            "status": "error",
            "message": str(e)
        }
