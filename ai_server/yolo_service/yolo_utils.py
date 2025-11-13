"""
YOLO 모델 유틸리티
- 모델 로드, 추론, 후처리
- CPU 환경 전용 최적화 버전
"""

from pathlib import Path

import cv2
import numpy as np
import torch
from loguru import logger


def load_yolo_model(model_path: str):
    """
    YOLO 모델 로드 (CPU 전용)
    - 커스텀 모델(C3k2 등) 지원을 위해 force_reload=True 사용
    """
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"YOLO 모델 파일이 존재하지 않습니다: {model_path}")

    try:
        logger.info(f"📦 YOLO 모델 로드 중... ({model_path})")

        # 방법 1: torch.hub.load with force_reload=True (커스텀 모듈 지원)
        try:
            model = torch.hub.load(
                "ultralytics/yolov5",
                "custom",
                path=str(model_path),
                force_reload=True,  # 캐시 무시하고 강제 재로드
                trust_repo=True,  # 신뢰된 저장소로 처리
            )
        except Exception as e1:
            logger.warning(f"torch.hub.load 실패, ultralytics YOLO로 재시도: {e1}")
            # 방법 2: ultralytics YOLO 클래스 직접 사용
            try:
                from ultralytics import YOLO

                model = YOLO(str(model_path))
            except Exception as e2:
                logger.warning(f"ultralytics YOLO 로드 실패, torch.hub.load 재시도: {e2}")
                # 방법 3: torch.hub.load with force_reload=True 재시도
                model = torch.hub.load(
                    "ultralytics/yolov5",
                    "custom",
                    path=str(model_path),
                    force_reload=True,
                    trust_repo=True,
                    source="github",  # GitHub에서 직접 다운로드
                )

        # 모델 설정
        if hasattr(model, "conf"):
            model.conf = 0.75  # confidence threshold
        if hasattr(model, "iou"):
            model.iou = 0.45
        if hasattr(model, "max_det"):
            model.max_det = 50
        if hasattr(model, "classes"):
            model.classes = None  # 전체 클래스 사용

        # CPU로 이동 및 평가 모드
        if hasattr(model, "to"):
            model = model.to("cpu")
        if hasattr(model, "eval"):
            model.eval()

        logger.info("✅ YOLO 모델 로드 완료 (CPU)")
        return model
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"YOLO 모델 로드 실패: {e}") from e


def yolo_infer(model, frame: np.ndarray, return_boxes=False):
    """
    YOLO 모델 추론 (단일 프레임)
    Args:
        model: torch 모델 또는 ultralytics YOLO 모델 (load_yolo_model 반환)
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

        # 모델 타입 확인 (ultralytics YOLO vs torch.hub YOLO)
        try:
            from ultralytics import YOLO as UltralyticsYOLO

            if isinstance(model, UltralyticsYOLO):
                # ultralytics YOLO 클래스 사용
                results = model(img, conf=0.75, iou=0.45, max_det=50, verbose=False)

                if len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
                    return None if not return_boxes else []

                # 결과 파싱
                boxes_data = results[0].boxes
                if not return_boxes:
                    # 가장 높은 confidence의 label 반환
                    confidences = boxes_data.conf.cpu().numpy()
                    max_idx = confidences.argmax()
                    label = results[0].names[int(boxes_data.cls[max_idx])]
                    return str(label)
                boxes = []
                for i in range(len(boxes_data)):
                    box = boxes_data.xyxy[i].cpu().numpy()
                    conf = float(boxes_data.conf[i].cpu().numpy())
                    cls = int(boxes_data.cls[i].cpu().numpy())
                    label = results[0].names[cls]
                    boxes.append(
                        {
                            "label": str(label),
                            "confidence": conf,
                            "box": [float(box[0]), float(box[1]), float(box[2]), float(box[3])],
                        }
                    )
                return boxes
        except ImportError:
            # ultralytics가 없는 경우 (fallback)
            pass

        # torch.hub.load YOLO (기존 방식)
        results = model(img, size=640)
        df = results.pandas().xyxy[0]

        if df.empty:
            return None if not return_boxes else []

        if not return_boxes:
            # 가장 높은 confidence의 label 반환
            top = df.iloc[df["confidence"].idxmax()]
            return str(top["name"])
        boxes = []
        for _, row in df.iterrows():
            boxes.append(
                {
                    "label": str(row["name"]),
                    "confidence": float(row["confidence"]),
                    "box": [float(row["xmin"]), float(row["ymin"]), float(row["xmax"]), float(row["ymax"])],
                }
            )
        return boxes

    except Exception as e:  # pragma: no cover
        logger.error(f"YOLO 추론 오류: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None

