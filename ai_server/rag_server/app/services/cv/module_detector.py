"""
모듈 탐지 서비스
- 최근 프레임(보통 3~5장)을 받아 YOLO로 fan, belt, gauge 등 모듈 감지
- 가장 확신(confidence)이 높은 결과만 추출
"""

import asyncio
# import torch
# from ultralytics import YOLO
import numpy as np
from loguru import logger

# YOLO 모델 캐시
_yolo_module_model = None


def get_module_model():
    """YOLO 모듈 탐지 모델 (lazy load, 단일 인스턴스)"""
    global _yolo_module_model
    if _yolo_module_model is None:
        logger.warning("⚠️ [module_detector] 테스트 모드: YOLO 로드 과정 비활성화")
        # logger.info("📦 [module_detector] YOLO 모델 로드 중...")
        # _yolo_module_model = YOLO("/app/models/module_best.pt")
        # _yolo_module_model.fuse()  # CPU 최적화
        # logger.info("✅ [module_detector] YOLO 모델 로드 완료")
        _yolo_module_model = False  # 테스트용 플래그
    return _yolo_module_model


async def detect_modules_from_recent_frames(frames: list[np.ndarray]):
    """
    최근 프레임에서 모듈(fan, belt, gauge 등) 탐지
    Args:
        frames: 최근 프레임 리스트
    Returns:
        detections: [{"label": str, "confidence": float}]
    """
    if not frames:
        return []

    model = get_module_model()
    if not model:
        logger.info("⏭️ [module_detector] 테스트 모드로 인해 YOLO 탐지 스킵")
        return []

    # YOLO는 내부적으로 GIL을 잠그므로, 비동기화하려면 to_thread 사용이 필수
    # tasks = [
    #     asyncio.to_thread(model.predict, f, imgsz=640, conf=0.35, verbose=False)
    #     for f in frames
    # ]
    # results_batches = await asyncio.gather(*tasks)

    # detections = []
    # for results in results_batches:
    #     for res in results:
    #         boxes = res.boxes
    #         for box in boxes:
    #             label = model.names[int(box.cls)]
    #             conf = float(box.conf)
    #             detections.append({"label": label, "confidence": conf})

    # # 중복 제거 및 최고 신뢰도 선택
    # filtered = _filter_top_detections(detections)
    # logger.info(f"🔍 [module_detector] 탐지된 모듈 수: {len(filtered)}개")
    # return filtered
    return []


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
