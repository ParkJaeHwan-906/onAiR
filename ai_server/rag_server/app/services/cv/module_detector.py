"""
모듈 탐지 서비스
- 최근 프레임(보통 1~3장)을 받아 YOLO로 fan, belt, gauge 등 모듈 감지
- 가장 확신(confidence)이 높은 결과만 추출
"""

from loguru import logger
import numpy as np
import os
from pathlib import Path
from ultralytics import YOLO

from app.services.cv.yolo_executor import YOLOContext, acquire_yolo_context

# YOLO 모델 캐시
_yolo_module_model = None


def get_module_model():
    """YOLO 모듈 탐지 모델 (lazy load, 단일 인스턴스)"""
    global _yolo_module_model
    if _yolo_module_model is None:
        try:
            model_path = "/app/models/module_best.pt"
            if not Path(model_path).exists():
                logger.warning(f"⚠️ [module_detector] 모델 파일이 없습니다: {model_path}")
                _yolo_module_model = False
            else:
                _yolo_module_model = YOLO(model_path)
                _yolo_module_model.fuse()
                logger.info("✅ [module_detector] YOLO 모듈 모델 로드 완료")
        except Exception as e:
            logger.error(f"❌ [module_detector] YOLO 모델 로드 실패: {e}")
            _yolo_module_model = False
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

    try:
        response = await infer_module(frames)
    except YOLOServiceError as err:
        logger.warning(f"[module_detector] YOLO 서비스 오류(code={err.code}, message={err.message})")
        return []


async def _get_module_model_async(ctx: YOLOContext):
    """모델 로드를 별도 스레드에서 실행"""
    global _yolo_module_model
    if _yolo_module_model is not None and _yolo_module_model is not False:
        return _yolo_module_model
    
    def _load_model():
        global _yolo_module_model
        try:
            model_path = "/app/models/module_best.pt"
            if not Path(model_path).exists():
                logger.warning(f"⚠️ [module_detector] 모델 파일이 없습니다: {model_path}")
                _yolo_module_model = False
                return False
            else:
                _yolo_module_model = YOLO(model_path)
                _yolo_module_model.fuse()
                logger.info("✅ [module_detector] YOLO 모듈 모델 로드 완료")
                return True
        except Exception as e:
            logger.error(f"❌ [module_detector] YOLO 모델 로드 실패: {e}")
            _yolo_module_model = False
            return False
    
    success = await ctx.run(_load_model)
    return _yolo_module_model if success else None


async def _detect_with_context(
    ctx: YOLOContext,
    model,
    frames: list[np.ndarray],
):
    """YOLO 모델로 프레임에서 모듈 탐지"""
    detections = []
    
    def _infer():
        nonlocal detections
        for frame in frames:
            results = model.predict(frame, imgsz=640, conf=0.35, verbose=False)
            for res in results:
                for box in res.boxes:
                    label = model.names[int(box.cls)]
                    conf = float(box.conf)
                    detections.append({"label": label, "confidence": conf})
    
    await ctx.run(_infer)
    
    # 중복 제거 및 최고 신뢰도 선택
    return _filter_top_detections(detections)


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
