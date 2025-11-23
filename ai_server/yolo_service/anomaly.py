import cv2
import numpy as np
from loguru import logger
from ultralytics import YOLO

from ai_server.yolo_service.redis_client import (
    get_device_state, get_latest_yolo_result,
    get_latest_frame, get_cv_buffer_frames
)
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


# -----------------------------------------------------
# ★ 정제 로직 (status 기반)
# -----------------------------------------------------
def _filter_anomalies(anomalies: dict):
    """status not_found/error/unknown 제거, 의미 있는 anomaly만 유지"""
    filtered = {}
    for key, item in anomalies.items():
        status = item.get("status")

        if status in ("not_found", "error", "unknown"):
            continue

        filtered[key] = item

    return filtered


def _collect_messages(anomalies: dict):
    """정상/이상 상태만 message 추출"""
    msgs = []
    for key, item in anomalies.items():
        status = item.get("status")

        if status in ("not_found", "error", "unknown"):
            continue

        msg = item.get("message")
        if msg:
            msgs.append(msg)

    return msgs


# -----------------------------------------------------
# ★ 메인 로직
# -----------------------------------------------------
async def run_anomaly_detection():
    logger.info("🚀 anomaly_detection() 시작")

    # -------------------------
    # 0) Device 확인
    # -------------------------
    device = await get_device_state()
    device_label = device["label"] if device else None

    if device_label != "AHU":
        return {
            "detected": False,
            "has_anomaly": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "message": "AHU가 아님",
            "modules_detected": False  # ★ 추가
        }

    # -------------------------
    # 1) YOLO 결과
    # -------------------------
    yolo_data = await get_latest_yolo_result()
    if not yolo_data:
        return {
            "detected": False,
            "has_anomaly": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "message": "YOLO 결과 없음",
            "modules_detected": False  # ★ 추가
        }

    raw_boxes = yolo_data.get("boxes", [])
    latest_ts = yolo_data.get("frame_ts")

    # 예측된 모듈들
    fan_belt_boxes = [b for b in raw_boxes if b["label"] in FAN_BELT_CLASSES]
    gauge_boxes = [b for b in raw_boxes if b["label"] in ("pressure_gauge", "thermometer")]
    panel_boxes = [b for b in raw_boxes if b["label"] == "control_panel"]
    panel_parts_boxes = [b for b in raw_boxes if b["label"] in PANEL_parts]

    anomalies = {}
    modules_detected = False  # ★ 모듈 탐지 여부 플래그

    # -------------------------
    # 2) Fan/Belt 분석
    # -------------------------
    if fan_belt_boxes:
        modules_detected = True  # ★ 모듈 탐지됨
        frames = await get_cv_buffer_frames(60)
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
        anomalies["fan_belt"] = {"status": "not_found"}

    # -------------------------
    # 3) 최신 프레임 확보
    # -------------------------
    latest_frame, _ = await get_latest_frame()
    if latest_frame is None:
        return {
            "detected": False,
            "has_anomaly": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": anomalies,
            "message": "프레임 없음",
            "modules_detected": False
        }

    # -------------------------
    # 4) Gauge 분석
    # -------------------------
    if gauge_boxes:
        modules_detected = True  # ★ 모듈 탐지됨
        anomalies["gauge"] = await analyze_gauge(latest_frame, gauge_boxes)
    else:
        anomalies["gauge"] = {"status": "not_found"}

    # -------------------------
    # 5) Panel 분석
    # -------------------------
    if panel_boxes:
        modules_detected = True  # ★ 모듈 탐지됨
        anomalies["panel"] = await analyze_panel(latest_frame, panel_boxes, panel_parts_boxes)
    else:
        anomalies["panel"] = {"status": "not_found"}

    # -------------------------
    # 6) 이상 판단
    # -------------------------
    has_anomaly = any(v.get("status") == "anomaly" for v in anomalies.values())

    # -------------------------
    # 7) ★ 여기서 정제 수행
    # -------------------------
    filtered_anomalies = _filter_anomalies(anomalies)
    filtered_messages = _collect_messages(filtered_anomalies)

    # -------------------------
    # 8) 최종 반환
    # ★ detected = modules_detected로 동일하게 맞춤
    # -------------------------
    return {
        "detected": modules_detected,  # ★ modules_detected와 동일하게 설정
        "has_anomaly": has_anomaly,
        "device_type": device_label,
        "timestamp": latest_ts,
        "modules": raw_boxes,
        "anomalies": filtered_anomalies,   # 정제된 anomaly
        "messages": filtered_messages,     # 정제된 메시지
        "message": "OK",
        "modules_detected": modules_detected
    }
