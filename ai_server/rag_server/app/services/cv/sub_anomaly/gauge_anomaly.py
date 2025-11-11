"""
게이지 이상 탐지 (YOLO + Sharpness 기반 단일 프레임 분석)
- Redis로부터 전달된 프레임 중 가장 선명한 이미지를 선택
- thermometer / pressure_gauge 지침 각도를 계산
- 단일 프레임 기준으로 이상 여부를 판단
"""

import os
import cv2
import numpy as np
from ultralytics import YOLO
from loguru import logger

# ---------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "../../../models/module_best.pt")

# ---------------------------------------------------------
# 하이퍼파라미터
# ---------------------------------------------------------
MIN_SHARPNESS = 70.0  # 흐림 필터 기준값


# ---------------------------------------------------------
# 유틸리티 함수
# ---------------------------------------------------------
def calc_sharpness(frame: np.ndarray) -> float:
    """Laplacian variance 기반 선명도 계산"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def detect_gauge_value_fast(img: np.ndarray):
    """Hough 원 기반 지침 각도 계산"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, 1, 200,
        param1=100, param2=22, minRadius=50, maxRadius=0
    )
    if circles is None:
        return None, None

    x0, y0, R = np.uint16(np.around(circles[0][0]))
    edges = cv2.Canny(blur, 50, 150)
    h, w = gray.shape

    thetas = np.deg2rad(np.arange(0, 360, 2))
    scores = []
    for th in thetas:
        xs = (x0 + np.cos(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
        ys = (y0 - np.sin(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
        xs, ys = np.clip(xs, 0, w - 1), np.clip(ys, 0, h - 1)
        scores.append(edges[ys, xs].sum())

    if not scores:
        return None, None

    angle = np.rad2deg(thetas[np.argmax(scores)]) % 360
    return angle, None


def judge_abnormal(sensor_type: str, value: float):
    """온도계 / 압력계별 임계값 판단"""
    if sensor_type == "thermometer":
        if value > 80:
            return "온도 과열 경고", "high"
        if value < 5:
            return "온도 너무 낮음", "low"
        return "정상", "normal"
    elif sensor_type == "pressure_gauge":
        if value > 1.5:
            return "압력 과다", "high"
        if value < 0.2:
            return "압력 부족", "low"
        return "정상", "normal"
    return "Unknown type", "unknown"


# ---------------------------------------------------------
# 메인 분석 함수
# ---------------------------------------------------------
async def analyze_gauge(frames: list[np.ndarray]):
    """
    게이지 이상 탐지
    - 가장 선명한 1장만 YOLO에 입력
    - thermometer / pressure_gauge 분석
    """
    try:
        if not frames:
            return {
                "type": "gauge",
                "status": "unknown",
                "message": "입력 프레임 없음"
            }

        # 1️⃣ sharpness 계산 및 필터링
        sharpness_scores = [calc_sharpness(f) for f in frames]
        valid_frames = [(f, s) for f, s in zip(frames, sharpness_scores) if s > MIN_SHARPNESS]
        if not valid_frames:
            return {
                "type": "gauge",
                "status": "low_confidence",
                "message": "모든 프레임이 흐림 (선명도 부족)"
            }

        # 2️⃣ 가장 선명한 프레임 선택
        sharpest_frame, best_score = max(valid_frames, key=lambda x: x[1])

        # 3️⃣ YOLO 탐지 (단 1회)
        model = YOLO(MODEL_PATH)
        results = model.predict(sharpest_frame, conf=0.5, device="cpu", verbose=False)

        outputs = []
        for r in results[0].boxes:
            cls = model.names[int(r.cls)]
            if cls not in ("thermometer", "pressure_gauge"):
                continue

            x1, y1, x2, y2 = map(int, r.xyxy[0])
            crop = sharpest_frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            h, w = crop.shape[:2]
            if max(h, w) < 120:
                continue

            angle, _ = detect_gauge_value_fast(crop)
            if angle is not None:
                outputs.append((cls, angle))

        # 4️⃣ 결과 없으면 fallback
        if not outputs:
            return {
                "type": "gauge",
                "status": "low_confidence",
                "message": "게이지 탐지 실패 또는 각도 검출 불가"
            }

        # 5️⃣ 이상 여부 판단
        result_by_type = {}
        for cls in set(c for c, _ in outputs):
            angles = [a for c, a in outputs if c == cls]
            mean_angle = np.mean(angles)
            ratio = (mean_angle - 230) / 90
            value = np.clip(ratio * (100 if cls == "thermometer" else 2), 0, None)
            msg, status = judge_abnormal(cls, value)
            result_by_type[cls] = {
                "angle": round(mean_angle, 2),
                "value": round(value, 2),
                "status": status,
                "message": msg
            }

        logger.info(f"[gauge] Sharpness={best_score:.2f}, 결과={result_by_type}")
        return {
            "type": "gauge",
            "status": "done",
            "sharpness": best_score,
            "results": result_by_type
        }

    except Exception as e:
        logger.exception(f"[gauge] 분석 중 오류: {e}")
        return {
            "type": "gauge",
            "status": "error",
            "message": str(e)
        }
