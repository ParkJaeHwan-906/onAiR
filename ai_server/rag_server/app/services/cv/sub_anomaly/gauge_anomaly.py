"""
게이지 이상 탐지 (YOLO + Sharpness 기반 단일 프레임 분석)
- Redis로부터 전달된 프레임 중 가장 선명한 이미지를 선택
- thermometer / pressure_gauge 지침 각도를 계산
- 단일 프레임 기준으로 이상 여부를 판단
"""

import os
import cv2
import numpy as np
from pathlib import Path
from loguru import logger
from ultralytics import YOLO

from app.services.cv.yolo_executor import YOLOContext, acquire_yolo_context

# ---------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = "/app/models/module_best.pt"

_yolo_gauge_model = None

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
async def analyze_gauge(
    frames: list[np.ndarray],
    yolo_ctx: YOLOContext | None = None,
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

        if yolo_ctx is None:
            async with acquire_yolo_context() as ctx:
                return await _analyze_with_context(ctx, sharpest_frame, best_score)
        return await _analyze_with_context(yolo_ctx, sharpest_frame, best_score)

    except Exception as e:
        logger.exception(f"[gauge] 분석 중 오류: {e}")
        return {
            "type": "gauge",
            "status": "error",
            "message": str(e)
        }


async def _analyze_with_context(
    ctx: YOLOContext,
    sharpest_frame: np.ndarray,
    best_score: float,
):
    """YOLO 모델을 사용한 게이지 이상 탐지"""
    global _yolo_gauge_model
    
    # 모델 로드 (lazy load)
    if _yolo_gauge_model is None:
        try:
            if Path(MODEL_PATH).exists():
                _yolo_gauge_model = YOLO(MODEL_PATH)
                _yolo_gauge_model.fuse()
                logger.info("✅ [gauge] YOLO 모델 로드 완료")
            else:
                logger.warning(f"⚠️ [gauge] 모델 파일이 없습니다: {MODEL_PATH}")
                return {"type": "gauge", "status": "error", "message": "모델 파일 없음", "sharpness": best_score}
        except Exception as e:
            logger.error(f"❌ [gauge] 모델 로드 실패: {e}")
            return {"type": "gauge", "status": "error", "message": f"모델 로드 실패: {e}", "sharpness": best_score}
    
    # YOLO로 게이지 탐지
    def _detect_gauges():
        results = _yolo_gauge_model.predict(sharpest_frame, conf=0.5, device="cpu", verbose=False)
        gauge_detections = []
        for r in results:
            for box in r.boxes:
                cls = _yolo_gauge_model.names[int(box.cls)]
                if "gauge" in cls.lower() or "thermometer" in cls.lower() or "pressure" in cls.lower():
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    roi = sharpest_frame[y1:y2, x1:x2]
                    gauge_detections.append({"type": cls, "roi": roi})
        return gauge_detections
    
    gauge_detections = await ctx.run(_detect_gauges)
    
    if not gauge_detections:
        return {"type": "gauge", "status": "not_found", "message": "게이지 미검출", "sharpness": best_score, "results": {}}
    
    # 각 게이지 분석
    results = {}
    has_anomaly = False
    
    for det in gauge_detections:
        gauge_type = det["type"]
        roi = det["roi"]
        
        angle, _ = detect_gauge_value_fast(roi)
        if angle is None:
            continue
        
        # 각도를 값으로 변환 (간단한 매핑)
        if "thermometer" in gauge_type.lower():
            # 온도계: 각도를 온도로 변환 (예시)
            value = (angle / 360.0) * 100  # 0-100도 범위로 가정
        elif "pressure" in gauge_type.lower():
            # 압력계: 각도를 압력으로 변환 (예시)
            value = (angle / 360.0) * 2.0  # 0-2.0 범위로 가정
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


def _get_gauge_model():
    return _yolo_gauge_model
