import cv2
import numpy as np
from loguru import logger
from ultralytics import YOLO

from ai_server.yolo_service.redis_client import get_device_state, get_latest_yolo_result, get_latest_frame, get_cv_buffer_frames
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

FAN_BELT_CLASSES = ("belt", "fan")


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

    device = await get_device_state()
    device_label = device["label"] if device else None
    if device_label != "AHU":
        return {
            "detected": False,
            "has_anomaly": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "message": "AHU가 아님"
        }

    yolo_data = await get_latest_yolo_result()
    if not yolo_data:
        return {
            "detected": False,
            "has_anomaly": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "message": "YOLO 결과 없음"
        }

    raw_boxes = yolo_data.get("boxes", [])
    latest_ts = yolo_data.get("frame_ts")

    # belt 또는 fan 하나라도 있으면 flow 분석 실행
    fan_belt_boxes = [b for b in raw_boxes if b["label"] in FAN_BELT_CLASSES]

    # gauge / panel
    gauge_boxes = [b for b in raw_boxes if b["label"] in ("pressure_gauge","thermometer")]
    panel_boxes = [b for b in raw_boxes if b["label"] in ("control_panel")]
    panel_parts_boxes = [b for b in raw_boxes if b["label"] in PANEL_parts]

    anomalies = {}

    # ▶ 팬/벨트 Flow 분석
    if fan_belt_boxes:
        frames = await get_cv_buffer_frames(30)
        if len(frames) < 10:
            anomalies["fan_belt"] = {
                "type": "fan_belt",
                "status": "error",
                "detail": "not_enough_frames",
                "message": "프레임 부족",
                "results": {}
            }
        else:
            anomalies["fan_belt"] = await analyze_fan_belt(frames, fan_belt_boxes)
    else:
        anomalies["fan_belt"] = { "status": "not_found" }

    # 최신 프레임
    latest_frame, _ = await get_latest_frame()
    if latest_frame is None:
        return {
            "detected": False,
            "has_anomaly": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": anomalies,
            "message": "프레임 없음"
        }

    # ▶ Gauge 분석
    if gauge_boxes:
        anomalies["gauge"] = await analyze_gauge(latest_frame, gauge_boxes)
    else:
        anomalies["gauge"] = { "status": "not_found" }

    # ▶ Panel 분석
    if panel_boxes:
        anomalies["panel"] = await analyze_panel(latest_frame, panel_boxes, panel_parts_boxes)
    else:
        anomalies["panel"] = { "status": "not_found" }

    # anomaly 판단
    has_anomaly = any(v.get("status") == "anomaly" for v in anomalies.values())

    return {
        "detected": True,
        "has_anomaly": has_anomaly,
        "device_type": device_label,
        "timestamp": latest_ts,
        "modules": raw_boxes,
        "anomalies": anomalies,
        "message": "OK"
    }
