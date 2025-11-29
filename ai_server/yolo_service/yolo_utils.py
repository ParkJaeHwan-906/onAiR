from typing import List, Optional
import numpy as np
from ultralytics import YOLO

def load_yolo_model(model_path: str):
    """
    YOLO 모델 로드
    """
    return YOLO(model_path)

def yolo_infer(
    model,
    frame: np.ndarray,
    return_boxes: bool = False,
    conf: float = 0.25,
    iou: float = 0.45
):
    # YOLO 호출에 conf / iou 직접 전달
    results = model(frame, conf=conf, iou=iou)

    detections = []

    for r in results:
        boxes = r.boxes
        if boxes is None or boxes.shape[0] == 0:
            continue

        for box in boxes:
            label_idx = int(box.cls[0])
            confidence = float(box.conf[0])
            label_name = model.names[label_idx]

            det = {
                "label": label_name,
                "confidence": confidence,
            }

            if return_boxes:
                xyxy = box.xyxy[0].cpu().numpy().tolist()
                det["x1"] = int(xyxy[0])
                det["y1"] = int(xyxy[1])
                det["x2"] = int(xyxy[2])
                det["y2"] = int(xyxy[3])

            detections.append(det)

    return detections
