
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

torch.set_num_threads(1)
torch.set_num_interop_threads(1)


def load_yolo_model(model_path: str):
    """
    YOLOv11n 모델 로드 (CPU 전용)
    """
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"YOLO 모델 파일이 존재하지 않습니다: {model_path}")

    try:
        logger.info(f"📦 YOLO 모델 로드 중... ({model_path})")
        model = torch.hub.load(
            "ultralytics/yolov5", "custom", path=str(model_path), force_reload=False
        )
        model.conf = 0.75  # confidence threshold
        model.iou = 0.45
        model.max_det = 50
        model.classes = None  # 전체 클래스 사용
        model.to("cpu").eval()
        logger.info("✅ YOLO 모델 로드 완료 (CPU)")
        return model
    except Exception as e:
        raise RuntimeError(f"YOLO 모델 로드 실패: {e}")


def yolo_infer(model, frame: np.ndarray, return_boxes=False):
    """
    YOLO 모델 추론 (단일 프레임)
    Args:
        model: torch 모델 (load_yolo_model 반환)
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
        # 이미지 전처리
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 추론
        results = model(img, size=640)
        df = results.pandas().xyxy[0]

        if df.empty:
            return None if not return_boxes else []

        if not return_boxes:
            # 가장 높은 confidence의 label 반환
            top = df.iloc[df["confidence"].idxmax()]
            return str(top["name"])
        else:
            boxes = []
            for _, row in df.iterrows():
                boxes.append({
                    "label": str(row["name"]),
                    "confidence": float(row["confidence"]),
                    "box": [float(row["xmin"]), float(row["ymin"]),
                            float(row["xmax"]), float(row["ymax"])]
                })
            return boxes

    except Exception as e:
        logger.error(f"YOLO 추론 오류: {e}")
        return None
