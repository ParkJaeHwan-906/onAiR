
"""
YOLO 모델 유틸리티
- 모델 로드, 추론, 후처리
- CPU 환경 전용 최적화 버전
"""

import torch
import cv2
import numpy as np
from pathlib import Path
from loguru import logger
from ultralytics import YOLO


def load_yolo_model(model_path: str):
    """
    YOLO 모델 로드 (CPU 전용)
    ultralytics.YOLO()를 사용하여 커스텀 아키텍처 모델도 로드 가능
    """
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"YOLO 모델 파일이 존재하지 않습니다: {model_path}")

    try:
        logger.info(f"📦 YOLO 모델 로드 중... ({model_path})")
        # ultralytics.YOLO()를 사용하여 커스텀 모델 로드
        # 이 방식은 커스텀 아키텍처(C3k2 등)를 포함한 모델도 로드 가능
        model = YOLO(str(model_path))
        model.fuse()  # CPU 최적화
        logger.info("✅ YOLO 모델 로드 완료 (CPU)")
        return model
    except Exception as e:
        raise RuntimeError(f"YOLO 모델 로드 실패: {e}")


def yolo_infer(model, frame: np.ndarray, return_boxes=False):
    """
    YOLO 모델 추론 (단일 프레임)
    Args:
        model: YOLO 모델 (load_yolo_model 반환, ultralytics.YOLO 인스턴스)
        frame: np.ndarray (BGR)
        return_boxes: True일 경우 (label, conf, [x1, y1, x2, y2]) 반환

    Returns:
        label (str) or (list of dict)
    """
    if model is None:
        raise ValueError("모델이 로드되지 않았습니다.")

    if frame is None or not isinstance(frame, np.ndarray):
        raise ValueError("유효하지 않은 프레임 입력")

    try:
        # ultralytics.YOLO()는 BGR 이미지를 직접 처리 가능
        # 추론 (conf, iou 설정)
        results = model.predict(
            frame,
            conf=0.75,
            iou=0.45,
            max_det=50,
            device="cpu",
            verbose=False
        )

        if not results or len(results) == 0:
            return None if not return_boxes else []

        # 첫 번째 결과 사용
        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            return None if not return_boxes else []

        if not return_boxes:
            # 가장 높은 confidence의 label 반환
            confidences = result.boxes.conf.cpu().numpy()
            best_idx = confidences.argmax()
            class_id = int(result.boxes.cls[best_idx])
            label = result.names[class_id]
            return label
        else:
            boxes = []
            for i in range(len(result.boxes)):
                box = result.boxes.xyxy[i].cpu().numpy()
                conf = float(result.boxes.conf[i].cpu().numpy())
                class_id = int(result.boxes.cls[i].cpu().numpy())
                label = result.names[class_id]
                boxes.append({
                    "label": label,
                    "confidence": conf,
                    "box": [float(box[0]), float(box[1]), float(box[2]), float(box[3])]
                })
            return boxes

    except Exception as e:
        logger.error(f"YOLO 추론 오류: {e}")
        return None
