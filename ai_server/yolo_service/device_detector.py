import asyncio
import cv2
import numpy as np
from loguru import logger
from collections import deque

from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer
from ai_server.yolo_service.redis_client import (
    save_device_state, get_device_state, get_latest_frame, save_yolo_result, get_cv_buffer_frames
)
from ai_server.yolo_service.config_all_model import ALL_MODEL_PATH, DEVICE_CLASSES
from ai_server.yolo_service.gauge_anomaly import detect_gauge_angle_fast, THERMO_CONFIG, PRESS_CONFIG
from ai_server.yolo_service.fan_belt_anomaly import analyze_fan_belt

DETECTION_INTERVAL = 0.5
CONF_THRESHOLD = 0.75
IOU_THRESHOLD = 0.55
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

    # YOLO bbox smoothing
    smoothing_buffers = {}

    # ROI 안정화 버퍼 (fan, thermometer, pressure_gauge)
    roi_buffers = {
        "fan": deque(maxlen=3),
        "thermometer": deque(maxlen=3),
        "pressure_gauge": deque(maxlen=3)
    }

    while True:
        try:
            # ------------------------
            # 1) 프레임 수신
            # ------------------------
            res = await get_latest_frame()
            if res is None:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            frame, ts = res if isinstance(res, tuple) else (res.get("frame"), res.get("ts"))
            if frame is None:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # ------------------------
            # 2) Gaussian Blur
            # ------------------------
            frame_blur = cv2.GaussianBlur(frame, (3, 3), 0)

            # ------------------------
            # 3) YOLO 추론
            # ------------------------
            detections = yolo_infer(
                _device_model,
                frame_blur,
                return_boxes=True,
                conf=CONF_THRESHOLD,
                iou=IOU_THRESHOLD
            )

            # ------------------------
            # 4) YOLO bbox smoothing
            # ------------------------
            smoothed_dets = []

            for d in detections:
                if "x1" not in d:
                    continue

                label = d["label"]
                bbox = np.array([d["x1"], d["y1"], d["x2"], d["y2"]], dtype=float)

                # smoothing 버퍼 생성
                if label not in smoothing_buffers:
                    smoothing_buffers[label] = deque(maxlen=3)

                smoothing_buffers[label].append(bbox)

                # smoothing 적용
                if len(smoothing_buffers[label]) > 1:
                    avg = np.mean(smoothing_buffers[label], axis=0)
                    d["x1"], d["y1"], d["x2"], d["y2"] = avg.tolist()

                smoothed_dets.append(d)

            detections = smoothed_dets

            # ------------------------
            # 5) 디텍션 처리 + ROI 안정화
            # ------------------------
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

                # ===================================================================
                # 📌 ROI 안정화 (fan / thermometer / pressure_gauge 공통 로직)
                # ===================================================================
                if label in roi_buffers:
                    raw_roi = np.array([x1, y1, x2, y2], dtype=float)
                    roi_buffers[label].append(raw_roi)

                    # sudden-jump threshold (fan은 12px, gauge는 6px)
                    jump_th = 12 if label == "fan" else 6

                    if len(roi_buffers[label]) >= 2:
                        prev = roi_buffers[label][-2]
                        dx = abs(prev[0] - x1)
                        dy = abs(prev[1] - y1)

                        # sudden jump → 이전 ROI fallback
                        if dx > jump_th or dy > jump_th:
                            x1, y1, x2, y2 = map(int, prev)
                        else:
                            avg = np.mean(roi_buffers[label], axis=0).astype(int)
                            x1, y1, x2, y2 = avg.tolist()

                    # 게이지류는 ROI 확장 (fan은 유지)
                    if label != "fan":
                        x1 = max(x1 - 2, 0)
                        y1 = max(y1 - 2, 0)
                        x2 = min(x2 + 2, frame_blur.shape[1])
                        y2 = min(y2 + 2, frame_blur.shape[0])

                # ===================================================================
                # thermometer 처리
                # ===================================================================
                if label == "thermometer":
                    roi = frame_blur[y1:y2, x1:x2]
                    angle_val = detect_gauge_angle_fast(roi, THERMO_CONFIG)

                    if angle_val is not None:
                        angle, value = angle_val
                        tval = round(float(value), 1)
                        final_value = tval
                        if tval > 40:
                            is_anomaly = True

                # ===================================================================
                # pressure gauge 처리
                # ===================================================================
                elif label == "pressure_gauge":
                    roi = frame_blur[y1:y2, x1:x2]
                    angle_val = detect_gauge_angle_fast(roi, PRESS_CONFIG)

                    if angle_val is not None:
                        angle, value = angle_val
                        pval = round(float(value), 2)
                        final_value = pval
                        if pval > 0.8 or pval < 0.2:
                            is_anomaly = True

                        logger.info(f"[PRESS] angle={angle:.2f}°, value={pval:.2f}")

                # ===================================================================
                # fan anomaly 처리
                # ===================================================================
                elif label == "fan":

                    buf = await get_cv_buffer_frames()
                    frames_buf = [
                        cv2.GaussianBlur(b["frame"], (3, 3), 0)
                        for b in buf if b.get("frame") is not None
                    ]

                    if len(frames_buf) < 10:
                        logger.warning("[FAN] 프레임 부족 - skip")
                        analyze_fan_belt_result = {
                            "type": "fan_belt",
                            "status": "error",
                            "detail": "not_enough_frames",
                            "message": "프레임 부족",
                            "percent": {}
                        }
                    else:
                        analyze_fan_belt_result = await analyze_fan_belt(
                            frames_buf,
                            [{"x1": x1, "y1": y1, "x2": x2, "y2": y2}]
                        )

                    is_anomaly = analyze_fan_belt_result.get("status") == "anomaly"

                    logger.info(
                        f"[FAN] result={analyze_fan_belt_result.get('result')}, "
                        f"status={analyze_fan_belt_result.get('status')}, "
                        f"detail={analyze_fan_belt_result.get('detail')}, "
                        f"msg={analyze_fan_belt_result.get('message')}"
                    )

                # 결과 저장
                all_boxes.append({
                    "label": display_label,
                    "confidence": conf,
                    "x1": x1, "y1": y1,
                    "x2": x2, "y2": y2,
                    "anomaly": is_anomaly,
                    "value": final_value
                })

            await save_yolo_result(ts, all_boxes)

            # ------------------------
            # 6) 디바이스 후보 안정화
            # ------------------------
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
            else:
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
