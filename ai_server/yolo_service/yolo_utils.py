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
    YOLO 추론 + 후처리
    - return_boxes=True → x1,y1,x2,y2 를 flat 필드로 추가
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

            det = {
                "label": label_name,
                "confidence": confidence,
            }

            if return_boxes:
                # YOLO xyxy → numpy 변환 후 flatten
                xyxy = box.xyxy[0].cpu().numpy().tolist()

                det["x1"] = int(xyxy[0])
                det["y1"] = int(xyxy[1])
                det["x2"] = int(xyxy[2])
                det["y2"] = int(xyxy[3])

            detections.append(det)

    return detections