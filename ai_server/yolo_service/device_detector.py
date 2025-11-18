# yolo_service/device_detector.py

import asyncio
from loguru import logger
from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer
from ai_server.yolo_service.redis_client import (
    save_device_state, get_device_state, get_latest_frame, save_yolo_result
)
from ai_server.yolo_service.config_all_model import ALL_MODEL_PATH, DEVICE_CLASSES

DETECTION_INTERVAL = 2.0
CONF_THRESHOLD = 0.75
STABLE_COUNT_REQUIRED = 5

_device_model = None


async def device_detector_loop():
    global _device_model
    _device_model = load_yolo_model(ALL_MODEL_PATH)
    logger.info("[device_monitor] 📡 디바이스 감지 루프 시작")

    info = await get_device_state()
    prev_state = info["label"] if info else None
    candidate_label = None
    stable_counter = 0

    while True:
        try:
            res = await get_latest_frame()
            if res is None:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            frame, ts = res if isinstance(res, tuple) else (res.get("frame"), res.get("ts"))
            if frame is None:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            detections = yolo_infer(_device_model, frame, return_boxes=False)

            # YOLO 박스 표준 스키마로 변환
            all_boxes = []
            for d in detections:
                box = d["box"]  # YOLO util 에서 dict로 들어옴
                all_boxes.append({
                    "label": d["label"],
                    "confidence": float(d["confidence"]),
                    "x1": int(box["x1"]),
                    "y1": int(box["y1"]),
                    "x2": int(box["x2"]),
                    "y2": int(box["y2"]),
                })

            await save_yolo_result(ts, all_boxes)

            # 디바이스 후보
            device_candidates = [
                d for d in detections
                if d["label"] in DEVICE_CLASSES and d["confidence"] >= CONF_THRESHOLD
            ]

            if not device_candidates:
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            top = max(device_candidates, key=lambda d: d["confidence"])
            label, confidence = top["label"], top["confidence"]

            if label == prev_state:
                candidate_label = None
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            if candidate_label != label:
                candidate_label = label
                stable_counter = 1
            else:
                stable_counter += 1

            if stable_counter >= STABLE_COUNT_REQUIRED:
                prev_state = candidate_label
                await save_device_state(prev_state, confidence)
                candidate_label = None
                stable_counter = 0

        except Exception as e:
            logger.exception(f"[device_monitor] 🚨 오류: {e}")

        await asyncio.sleep(DETECTION_INTERVAL)
