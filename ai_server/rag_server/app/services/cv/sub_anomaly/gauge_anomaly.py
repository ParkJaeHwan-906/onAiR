"""
게이지 이상 탐지 (YOLO 서비스 연동 + Sharpness 기반 단일 프레임 분석)
- 프레임 중 가장 선명한 이미지를 선택
- YOLO 서비스로 thermometer / pressure_gauge 영역 추출
- 단일 프레임 기준으로 이상 여부를 판단
"""

import cv2
import numpy as np
from loguru import logger

from app.services.cv.yolo_client import YOLOServiceError, infer_module

MIN_SHARPNESS = 70.0  # 흐림 필터 기준값


def calc_sharpness(frame: np.ndarray) -> float:
    """Laplacian variance 기반 선명도 계산"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def detect_gauge_value_fast(img: np.ndarray):
    """Hough 원 기반 지침 각도 계산"""
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
    if sensor_type == "pressure_gauge":
        if value > 1.5:
            return "압력 과다", "high"
        if value < 0.2:
            return "압력 부족", "low"
        return "정상", "normal"
    return "Unknown type", "unknown"


async def analyze_gauge(
    frames: list[np.ndarray],
):
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
                "message": "입력 프레임 없음",
            }

        sharpness_scores = [calc_sharpness(f) for f in frames]
        valid_frames = [(f, s) for f, s in zip(frames, sharpness_scores) if s > MIN_SHARPNESS]
        if not valid_frames:
            return {
                "type": "gauge",
                "status": "low_confidence",
                "message": "모든 프레임이 흐림 (선명도 부족)",
            }

        sharpest_frame, best_score = max(valid_frames, key=lambda x: x[1])

        module_resp = await infer_module([sharpest_frame])
        detections = module_resp.get("frames", [[]])[0] if module_resp.get("frames") else []

        gauge_detections = []
        for det in detections:
            label = det.get("label", "")
            if any(key in label.lower() for key in ("gauge", "thermometer", "pressure")):
                box = det.get("box")
                if box:
                    x1, y1, x2, y2 = [int(v) for v in box]
                    roi = sharpest_frame[y1:y2, x1:x2]
                    if roi.size > 0:
                        gauge_detections.append({"type": label, "roi": roi})

        if not gauge_detections:
            return {
                "type": "gauge",
                "status": "not_found",
                "message": "게이지 미검출",
                "sharpness": best_score,
                "results": {},
            }

        results = {}
        has_anomaly = False

        for det in gauge_detections:
            gauge_type = det["type"]
            roi = det["roi"]

            angle, _ = detect_gauge_value_fast(roi)
            if angle is None:
                continue

            if "thermometer" in gauge_type.lower():
                value = (angle / 360.0) * 100
            elif "pressure" in gauge_type.lower():
                value = (angle / 360.0) * 2.0
            else:
                value = angle / 360.0

            msg, status = judge_abnormal(gauge_type, value)

            results[gauge_type] = {
                "value": float(value),
                "angle": float(angle),
                "status": status,
                "message": msg,
            }

            if status != "normal":
                has_anomaly = True

        return {
            "type": "gauge",
            "status": "anomaly" if has_anomaly else "normal",
            "sharpness": best_score,
            "results": results,
            "message": "이상 탐지됨" if has_anomaly else "정상",
        }

    except YOLOServiceError as err:
        logger.warning(f"[gauge] YOLO 서비스 오류: {err.code} ({err.message})")
        return {
            "type": "gauge",
            "status": "error",
            "message": err.message,
        }
    except Exception as e:  # pragma: no cover
        logger.exception(f"[gauge] 분석 중 오류: {e}")
        return {
            "type": "gauge",
            "status": "error",
            "message": str(e),
        }
