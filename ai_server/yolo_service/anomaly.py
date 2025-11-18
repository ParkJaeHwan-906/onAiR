import cv2
import numpy as np
from loguru import logger
from ultralytics import YOLO

from ai_server.yolo_service.redis_client import get_device_state, get_latest_yolo_result, get_latest_frame
from ai_server.yolo_service.fan_belt_anomaly import analyze_fan_belt
from ai_server.yolo_service.gauge_anomaly import analyze_gauge
from ai_server.yolo_service.panel_anomaly import analyze_panel
from ai_server.yolo_service.config_all_model import ALL_MODEL_PATH, MODULE_CLASSES, PANEL_parts
from ai_server.yolo_service.device_detector import _device_model

MODULE_MODEL_PATH = ALL_MODEL_PATH
_module_model = None

MIN_SHARPNESS = 70.0
MIN_CONF = 0.70
MIN_BOX_AREA = 15000

TOTAL_FRAMES = 30
SHARPNESS_FRAMES = 10

def calc_sharpness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def format_boxes(results, names):
    boxes = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf)
            label = names[int(box.cls)]
            area = (x2 - x1) * (y2 - y1)

            boxes.append({
                "label": label,
                "confidence": conf,
                "x1": x1, "y1": y1,
                "x2": x2, "y2": y2,
                "area": area
            })
    return boxes


async def run_anomaly_detection():
    logger.info("🚀 anomaly_detection() 시작")

    # 1) 장비 타입 확인
    device_info = await get_device_state()
    device_label = device_info.get("label") if device_info else None

    if device_label != "AHU":
        return {
            "detected": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "message": "AHU가 아님"
        }

    # 2) 최신 프레임 가져오기
    frame, frame_ts = await get_latest_frame()
    if frame is None:
        return {
            "detected": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "message": "프레임 없음"
        }

    # 3) YOLO 박스 가져오기
    yolo_data = await get_latest_yolo_result()
    if not yolo_data:
        return {
            "detected": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "message": "YOLO 결과 없음"
        }

    raw_boxes = yolo_data.get("boxes", [])
    latest_ts = yolo_data.get("frame_ts")

    logger.info(f"📦 YOLO 박스 {len(raw_boxes)}개 가져옴 (ts={latest_ts})")

    # 4) 박스 분류
    module_boxes = [b for b in raw_boxes if b["label"] in MODULE_CLASSES]
    panel_boxes = [b for b in raw_boxes if b["label"] in ("control_panel", "AHU_pannel")]
    panel_parts_boxes = [b for b in raw_boxes if b["label"] in PANEL_parts]

    gauge_boxes = [
        b for b in raw_boxes
        if b["label"] in ("pressure_gauge", "thermometer", "temperature_FND")
    ]

    belt_boxes = [b for b in raw_boxes if b["label"] == "belt"]

    # ---------------------------------------
    # 5) 이상 탐지 (표준 스키마)
    # ---------------------------------------
    anomalies = {}

    # Fan/Belt
    if belt_boxes:
        anomalies["fan_belt"] = await analyze_fan_belt([frame], belt_boxes)
    else:
        anomalies["fan_belt"] = {
            "type": "fan_belt",
            "status": "not_found",
            "detail": "no_belt_detected",
            "message": "벨트가 탐지되지 않음",
            "results": {}
        }

    # Gauge
    if gauge_boxes:
        anomalies["gauge"] = await analyze_gauge(frame, gauge_boxes)
    else:
        anomalies["gauge"] = {
            "type": "gauge",
            "status": "not_found",
            "detail": "no_gauge_detected",
            "message": "게이지가 탐지되지 않음",
            "results": {}
        }

    # Panel
    if panel_boxes:
        anomalies["panel"] = await analyze_panel(frame, panel_boxes, panel_parts_boxes)
    else:
        anomalies["panel"] = {
            "type": "panel",
            "status": "not_found",
            "detail": "no_panel_detected",
            "message": "제어판이 탐지되지 않음",
            "results": {}
        }

    # ---------------------------------------
    # 6) 최종 반환
    # ---------------------------------------
    return {
        "detected": True,
        "device_type": device_label,
        "timestamp": latest_ts,
        "modules": module_boxes,
        "anomalies": anomalies,
        "yolo_count": len(raw_boxes),
        "message": "OK"
    }
