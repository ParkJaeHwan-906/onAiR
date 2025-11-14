from typing import List, Optional
import numpy as np
from ultralytics import YOLO

def load_yolo_model(model_path: str):
    """
    YOLO 모델 로드
    """
    return YOLO(model_path)

def yolo_infer(model, frame: np.ndarray, return_boxes: bool = False):
    """
    YOLO 추론 실행 및 결과 후처리
    - model: YOLO 객체
    - frame: 추론할 이미지 (numpy array)
    - return_boxes: True일 경우 박스 정보 포함한 딕셔너리 반환
    """
    results = model(frame)

    detections = []

    for r in results:
        boxes = r.boxes
        if boxes is None or boxes.shape[0] == 0:
            continue

        for i in range(len(boxes)):
            box = boxes[i]
            label_idx = int(box.cls[0])
            confidence = float(box.conf[0])
            label_name = model.names[label_idx]

            detection = {
                "label": label_name,
                "confidence": confidence
            }

            if return_boxes:
                # box.xyxy[0]는 tensor → numpy로 변환
                xyxy = box.xyxy[0].cpu().numpy().tolist()
                detection["box"] = {
                    "x1": xyxy[0],
                    "y1": xyxy[1],
                    "x2": xyxy[2],
                    "y2": xyxy[3],
                }

            detections.append(detection)

    return detections