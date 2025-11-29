# yolo_service/device_detector.py

import asyncio
import cv2
import numpy as np
from loguru import logger
from collections import deque

from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer
from ai_server.yolo_service.redis_client import (
    save_device_state, get_device_state, get_latest_frame,
    save_yolo_result, get_cv_buffer_frames
)
from ai_server.yolo_service.config_all_model import ALL_MODEL_PATH, DEVICE_CLASSES
from ai_server.yolo_service.gauge_anomaly import detect_gauge_angle_fast, THERMO_CONFIG, PRESS_CONFIG
from ai_server.yolo_service.fan_belt_anomaly import analyze_fan_belt

DETECTION_INTERVAL = 0.5
CONF_THRESHOLD = 0.75
IOU_THRESHOLD = 0.55
STABLE_COUNT_REQUIRED = 5

# Gauge tuning
GAUGE_JUMP = 3
GAUGE_BUF = 2

_device_model = None


async def device_detector_loop():
    global _device_model
    _device_model = load_yolo_model(ALL_MODEL_PATH)
    logger.info("[device_monitor] 📡 디바이스 감지 루프 시작")

    info = await get_device_state()
    prev_state = info["label"] if info else None
    candidate_label = None
    stable_counter = 0

    # smoothing buffers
    smoothing_buffers = {}
    fan_roi_buffer = deque(maxlen=3)

    while True:
        try:
            # ---------------------------------------------------------
            # 1) 최신 프레임
            # ---------------------------------------------------------
            res = await get_latest_frame()
            if res is None:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            frame, ts = res if isinstance(res, tuple) else (res.get("frame"), res.get("ts"))
            if frame is None:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            frame_blur = cv2.GaussianBlur(frame, (3, 3), 0)

            # ---------------------------------------------------------
            # 2) YOLO 추론
            # ---------------------------------------------------------
            detections = yolo_infer(
                _device_model,
                frame_blur,
                return_boxes=True,
                conf=CONF_THRESHOLD,
                iou=IOU_THRESHOLD
            )

            # ---------------------------------------------------------
            # 3) Label 기반 smoothing (mean 기반)
            # → fan/기타용 공통 smoothing (게이지 제외)
            # ---------------------------------------------------------
            smoothed_dets = []
            for d in detections:
                if "x1" not in d:
                    continue
                label = d["label"]
                bbox = np.array([d["x1"], d["y1"], d["x2"], d["y2"]], dtype=float)

                # 게이지는 개별 로직에서 처리
                if label in ("thermometer", "pressure_gauge"):
                    smoothed_dets.append(d)
                    continue

                if label not in smoothing_buffers:
                    smoothing_buffers[label] = deque(maxlen=3)
                smoothing_buffers[label].append(bbox)

                if len(smoothing_buffers[label]) > 1:
                    avg = np.mean(smoothing_buffers[label], axis=0)
                    d["x1"], d["y1"], d["x2"], d["y2"] = avg.tolist()

                smoothed_dets.append(d)

            detections = smoothed_dets

            # ---------------------------------------------------------
            # 4) 박스 단위 처리
            # ---------------------------------------------------------
            all_boxes = []

            for d in detections:
                if "x1" not in d:
                    continue

                x1, y1, x2, y2 = map(int, [d["x1"], d["y1"], d["x2"], d["y2"]])
                label = d["label"]
                conf = float(d["confidence"])

                display_label = label
                is_anomaly = False
                final_value = None

                # -----------------------------------------------------
                # 4-1) thermometer (게이지)
                # -----------------------------------------------------
                if label == "thermometer":
                    raw = np.array([x1, y1, x2, y2], dtype=float)

                    if "thermometer" not in smoothing_buffers:
                        smoothing_buffers["thermometer"] = deque(maxlen=GAUGE_BUF)
                    smoothing_buffers["thermometer"].append(raw)

                    if len(smoothing_buffers["thermometer"]) >= 2:
                        prev = smoothing_buffers["thermometer"][-2]
                        dx = abs(prev[0] - x1)
                        dy = abs(prev[1] - y1)

                        if dx > GAUGE_JUMP or dy > GAUGE_JUMP:
                            med = np.median(smoothing_buffers["thermometer"], axis=0).astype(int)
                            x1, y1, x2, y2 = med.tolist()
                        else:
                            med = np.median(smoothing_buffers["thermometer"], axis=0).astype(int)
                            x1, y1, x2, y2 = med.tolist()

                    x1 = max(x1 - 2, 0)
                    y1 = max(y1 - 2, 0)
                    x2 = min(x2 + 2, frame.shape[1])
                    y2 = min(y2 + 2, frame.shape[0])

                    # 게이지는 blur 금지 → 원본 frame 사용
                    roi = frame[y1:y2, x1:x2]
                    angle_val = detect_gauge_angle_fast(roi, THERMO_CONFIG)

                    if angle_val:
                        angle, value = angle_val
                        temp_value = round(float(value), 1)
                        final_value = temp_value
                        if temp_value > 40:
                            is_anomaly = True

                # -----------------------------------------------------
                # 4-2) pressure gauge
                # -----------------------------------------------------
                elif label == "pressure_gauge":
                    raw = np.array([x1, y1, x2, y2], dtype=float)

                    if "pressure_gauge" not in smoothing_buffers:
                        smoothing_buffers["pressure_gauge"] = deque(maxlen=GAUGE_BUF)
                    smoothing_buffers["pressure_gauge"].append(raw)

                    if len(smoothing_buffers["pressure_gauge"]) >= 2:
                        prev = smoothing_buffers["pressure_gauge"][-2]
                        dx = abs(prev[0] - x1)
                        dy = abs(prev[1] - y1)

                        # sudden jump → median
                        if dx > GAUGE_JUMP or dy > GAUGE_JUMP:
                            med = np.median(smoothing_buffers["pressure_gauge"], axis=0).astype(int)
                            x1, y1, x2, y2 = med.tolist()
                        else:
                            med = np.median(smoothing_buffers["pressure_gauge"], axis=0).astype(int)
                            x1, y1, x2, y2 = med.tolist()

                    x1 = max(x1 - 2, 0)
                    y1 = max(y1 - 2, 0)
                    x2 = min(x2 + 2, frame.shape[1])
                    y2 = min(y2 + 2, frame.shape[0])

                    roi = frame[y1:y2, x1:x2]  # 원본 사용
                    angle_val = detect_gauge_angle_fast(roi, PRESS_CONFIG)

                    if angle_val:
                        angle, value = angle_val
                        press_value = round(float(value), 2)
                        final_value = press_value

                        if press_value > 0.8 or press_value < 0.2:
                            is_anomaly = True

                # -----------------------------------------------------
                # 4-3) fan (기존 안정화 로직 그대로 유지)
                # -----------------------------------------------------
                # elif label == "fan":
                #     fan_roi_buffer.append([x1, y1, x2, y2])

                #     if len(fan_roi_buffer) >= 2:
                #         prev = fan_roi_buffer[-2]
                #         dx = abs(prev[0] - x1)
                #         dy = abs(prev[1] - y1)
                #         if dx > 12 or dy > 12:
                #             x1, y1, x2, y2 = prev

                #     if len(fan_roi_buffer) > 1:
                #         avg = np.mean(fan_roi_buffer, axis=0).astype(int)
                #         x1, y1, x2, y2 = avg.tolist()

                    # buf = await get_cv_buffer_frames()

                    # # buf는 numpy array list임 → 안전하게 처리
                    # frames_buf = []
                    # for b in buf:
                    #     if isinstance(b, dict) and b.get("frame") is not None:
                    #         frames_buf.append(cv2.GaussianBlur(b["frame"], (3, 3), 0))
                    #     elif isinstance(b, np.ndarray):
                    #         frames_buf.append(cv2.GaussianBlur(b, (3, 3), 0))

                    # if len(frames_buf) < 10:
                    #     analyze_fan_belt_result = {
                    #         "type": "fan_belt",
                    #         "status": "error",
                    #         "detail": "not_enough_frames",
                    #         "message": "프레임 부족",
                    #         "percent": {}
                    #     }
                    # else:
                    #     analyze_fan_belt_result = await analyze_fan_belt(
                    #         frames_buf,
                    #         [{"x1": x1, "y1": y1, "x2": x2, "y2": y2}]
                    #     )

                    # is_anomaly = analyze_fan_belt_result.get("status") == "anomaly"

                # -----------------------------------------------------
                # 결과 push
                # -----------------------------------------------------
                all_boxes.append({
                    "label": display_label,
                    "confidence": conf,
                    "x1": x1, "y1": y1,
                    "x2": x2, "y2": y2,
                    "anomaly": is_anomaly,
                    "value": final_value
                })

            await save_yolo_result(ts, all_boxes)

            # ---------------------------------------------------------
            # 5) 디바이스 상태 안정화
            # ---------------------------------------------------------
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


async def start_device_detector():
    try:
        await device_detector_loop()
    except asyncio.CancelledError:
        logger.info("[device_monitor] start_device_detector Cancelled")
        raise
