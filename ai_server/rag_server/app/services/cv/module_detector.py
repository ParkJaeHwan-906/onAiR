"""
모듈 탐지 서비스
- 최근 프레임(보통 3~5장)을 받아 YOLO로 fan, belt, gauge 등 모듈 감지
- 가장 확신(confidence)이 높은 결과만 추출
"""

from ultralytics import YOLO
from loguru import logger
import numpy as np

from app.services.cv.yolo_executor import YOLOContext, acquire_yolo_context

# YOLO 모델 캐시
_yolo_module_model = None


def get_module_model():
    """YOLO 모듈 탐지 모델 (lazy load, 단일 인스턴스)"""
    global _yolo_module_model
    if _yolo_module_model is None:
        logger.info("📦 [module_detector] YOLO 모델 로드 중...")
        _yolo_module_model = YOLO("/app/models/module_best.pt")
        _yolo_module_model.fuse()  # CPU 최적화
        logger.info("✅ [module_detector] YOLO 모델 로드 완료")
    return _yolo_module_model


async def detect_modules_from_recent_frames(
    frames: list[np.ndarray],
    yolo_ctx: YOLOContext | None = None,
):
    """
    최근 프레임에서 모듈(fan, belt, gauge 등) 탐지
    Args:
        frames: 최근 프레임 리스트
        yolo_ctx: 단일 YOLO 스레드 컨텍스트 (없으면 내부에서 생성)
    Returns:
        detections: [{"label": str, "confidence": float}]
    """
    if not frames:
        return []

    model = get_module_model()

    if yolo_ctx is None:
        async with acquire_yolo_context() as ctx:
            return await _detect_with_context(ctx, model, frames)
    return await _detect_with_context(yolo_ctx, model, frames)


async def _detect_with_context(
    ctx: YOLOContext,
    model,
    frames: list[np.ndarray],
):
    results_batches = []
    for frame in frames:
        results = await ctx.run(model.predict, frame, imgsz=640, conf=0.35, verbose=False)
        results_batches.append(results)

    detections = []
    for results in results_batches:
        for res in results:
            boxes = res.boxes
            for box in boxes:
                label = model.names[int(box.cls)]
                conf = float(box.conf)
                detections.append({"label": label, "confidence": conf})

    filtered = _filter_top_detections(detections)
    logger.info(f"🔍 [module_detector] 탐지된 모듈 수: {len(filtered)}개")
    return filtered


def _filter_top_detections(detections, min_conf=0.4):
    """
    중복 모듈 제거 및 최고 신뢰도 결과만 반환
    """
    if not detections:
        return []

    result = {}
    for det in detections:
        label = det["label"]
        conf = det["confidence"]
        if conf < min_conf:
            continue
        if label not in result or conf > result[label]["confidence"]:
            result[label] = det
    return list(result.values())
