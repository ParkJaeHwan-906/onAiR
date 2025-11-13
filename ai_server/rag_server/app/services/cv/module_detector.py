"""
모듈 탐지 서비스 (YOLO 서비스 연동)
- 최근 프레임(보통 1~3장)을 YOLO 전용 서비스로 전달하여 fan, belt, gauge 등 모듈 감지
- 가장 확신(confidence)이 높은 결과만 추출
"""

from typing import List

import numpy as np
from loguru import logger

from app.services.cv.yolo_client import YOLOServiceError, infer_module


async def detect_modules_from_recent_frames(
    frames: List[np.ndarray],
):
    """
    최근 프레임에서 모듈(fan, belt, gauge 등) 탐지
    Args:
        frames: 최근 프레임 리스트
    Returns:
        detections: [{"label": str, "confidence": float}]
    """
    if not frames:
        return []

    try:
        response = await infer_module(frames)
    except YOLOServiceError as err:
        logger.warning(
            "[module_detector] YOLO 서비스 오류(code=%s, message=%s)",
            err.code,
            err.message,
        )
        return []

    raw_frames = response.get("frames", [])
    top_detections = response.get("top_detections", [])

    if top_detections:
        return _filter_top_detections(top_detections)

    flattened = [det for frame_dets in raw_frames for det in frame_dets]
    return _filter_top_detections(flattened)


def _filter_top_detections(detections, min_conf=0.4):
    """
    중복 모듈 제거 및 최고 신뢰도 결과만 반환
    """
    if not detections:
        return []

    result = {}
    for det in detections:
        label = det.get("label")
        conf = float(det.get("confidence", 0.0))
        if not label or conf < min_conf:
            continue
        if label not in result or conf > result[label]["confidence"]:
            result[label] = {"label": label, "confidence": conf}
    return list(result.values())
