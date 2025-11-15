import cv2
import numpy as np
from loguru import logger
from ultralytics import YOLO

from ai_server.yolo_service.redis_client import get_cv_buffer_frames, get_device_state
from ai_server.yolo_service.fan_belt_anomaly import analyze_fan_belt
from ai_server.yolo_service.gauge_anomaly import analyze_gauge
from ai_server.yolo_service.panel_anomaly import analyze_panel

MODULE_MODEL_PATH = "/app/ai_server/yolo_service/models/module_best.pt"
_module_model = None

MIN_SHARPNESS = 70.0
MIN_CONF = 0.70
MIN_BOX_AREA = 15000

TOTAL_FRAMES = 30
SHARPNESS_FRAMES = 10


def load_module_model():
    global _module_model
    if _module_model is None:
        _module_model = YOLO(MODULE_MODEL_PATH)
        _module_model.fuse()
        logger.info("module_best YOLO 로드 완료")
    return _module_model


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
                "xyxy": (x1, y1, x2, y2),
                "area": area
            })
    return boxes


async def run_anomaly_detection():
    logger.info("🚀 run_anomaly_detection() 시작")

    # 1) 장비 타입 확인
    device_info = await get_device_state()
    if not device_info:
        return {
            "detected": False,
            "device_type": None,
            "modules": [],
            "anomalies": {},
            "messages": [],
            "message": "디바이스 상태가 설정되지 않음"
        }

    device_label = device_info.get("label")
    if device_label != "AHU":
        return {
            "detected": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "messages": [],
            "message": "AHU가 아님"
        }

    # 2) 프레임 획득
    frames = await get_cv_buffer_frames(n=TOTAL_FRAMES)
    if not frames:
        return {
            "detected": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "messages": [],
            "message": "프레임 없음"
        }

    # 3) sharpest frame 선택
    sharp_frames = frames[:SHARPNESS_FRAMES]

    sharp_list = [(f, calc_sharpness(f)) for f in sharp_frames]
    sharp_list = [(f, s) for f, s in sharp_list if s > MIN_SHARPNESS]

    if not sharp_list:
        sharpest_frame, best_score = frames[-1], 0.0
    else:
        sharpest_frame, best_score = max(sharp_list, key=lambda x: x[1])

    logger.info(f"📸 sharpest sharpness={best_score:.1f}")

    # 4) YOLO 실행
    module_model = load_module_model()
    yolo_res = module_model.predict(sharpest_frame, conf=MIN_CONF, verbose=False)
    raw_boxes = format_boxes(yolo_res, module_model.names)

    module_boxes = [
        b for b in raw_boxes
        if b["confidence"] >= MIN_CONF and b["area"] >= MIN_BOX_AREA
    ]

    logger.info(f"📦 module boxes={module_boxes}")

    # 5) anomaly 모듈 실행
    fan_belt_result = await analyze_fan_belt(frames, sharpest_frame, best_score, module_boxes)
    gauge_result = await analyze_gauge(sharpest_frame, best_score, module_boxes)
    panel_result = await analyze_panel(sharpest_frame, best_score, module_boxes)

    anomalies = {
        "fan_belt": fan_belt_result,
        "gauge": gauge_result,
        "panel": panel_result
    }

    # 6) 모듈 메시지 수집
    collected_messages = []
    for key, res in anomalies.items():
        if isinstance(res, dict) and res.get("message"):
            collected_messages.append(res["message"])

    # 7) anomaly 여부 판정
    def is_abnormal(res):
        return res and res.get("status") == "anomaly"

    has_anomaly = any(is_abnormal(v) for v in anomalies.values())

    final_message = (
        " / ".join(collected_messages)
        if collected_messages else
        ("이상 탐지됨" if has_anomaly else "정상")
    )

    return {
        "detected": has_anomaly,
        "device_type": device_label,
        "modules": [{"label": b["label"], "confidence": b["confidence"]} for b in module_boxes],
        "anomalies": anomalies,
        "messages": collected_messages,     # 모든 모듈 메시지 배열
        "message": final_message            # 최종 자연 문장
    }
