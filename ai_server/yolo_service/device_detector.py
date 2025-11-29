# yolo_service/device_detector.py

import asyncio
from loguru import logger
from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer
from ai_server.yolo_service.redis_client import (
    save_device_state, get_device_state, get_latest_frame, save_yolo_result, get_cv_buffer_frames
)
from ai_server.yolo_service.config_all_model import ALL_MODEL_PATH, DEVICE_CLASSES
from ai_server.yolo_service.gauge_anomaly import detect_gauge_angle_fast, THERMO_CONFIG, PRESS_CONFIG
from ai_server.yolo_service.fan_belt_anomaly import analyze_fan_belt

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

            detections = yolo_infer(_device_model, frame, return_boxes=True)

            # YOLO 박스 표준 스키마로 변환
            all_boxes = []
            for d in detections:
                if "x1" in d and "y1" in d and "x2" in d and "y2" in d:

                    x1, y1, x2, y2 = map(int, [d["x1"], d["y1"], d["x2"], d["y2"]])
                    label = d["label"]
                    conf = float(d["confidence"])

                    display_label = label
                    temp_value = None

                    is_anomaly = False
                    final_value = None
                    # thermometer → 게이지 각도/값 계산
                    if label == "thermometer":
                        roi = frame[y1:y2, x1:x2]

                        angle_val = detect_gauge_angle_fast(roi, THERMO_CONFIG)
                        if angle_val is not None:
                            angle, value = angle_val
                            temp_value = round(float(value), 1)
                            if temp_value > 40:
                                is_anomaly = True
                            final_value = temp_value

                            
                    elif label == "pressure_gauge":
                        roi = frame[y1:y2, x1:x2]
                        angle_val = detect_gauge_angle_fast(roi, PRESS_CONFIG)
                        if angle_val is not None:
                            angle, value = angle_val
                            press_value = round(float(value), 2)

                            # 임계 판정
                            if press_value > 0.8 or press_value < 0.2:
                                is_anomaly = True
                            final_value = press_value
                            logger.info(f"[PRESS] angle={angle:.2f}°, value={press_value:.2f}")

                        elif label == "fan":
                            buf = await get_cv_buffer_frames()
                            frames_buf = [b["frame"] for b in buf if b.get("frame") is not None]

                            if len(frames_buf) < 10:
                                logger.warning("[FAN] 프레임 부족으로 분석 건너뜀")
                                analyze_fan_belt_result = {
                                    "type": "fan_belt",
                                    "status": "error",
                                    "detail": "not_enough_frames",
                                    "message": "프레임 부족",
                                    "percent": {}
                                }
                            else:
                                # 팬 ROI 좌표 전달
                                analyze_fan_belt_result = await analyze_fan_belt(
                                    frames_buf,
                                    [{
                                        "x1": x1, "y1": y1,
                                        "x2": x2, "y2": y2
                                    }]
                                )

                            # 결과 로그 출력
                            logger.info(
                                f"[FAN] result={analyze_fan_belt_result.get('result')}, "
                                f"status={analyze_fan_belt_result.get('status')}, "
                                f"detail={analyze_fan_belt_result.get('detail')}, "
                                f"msg={analyze_fan_belt_result.get('message')}"
                            )

                            # YOLO 결과에도 anomaly 여부 기록
                            is_anomaly = analyze_fan_belt_result.get("status") == "anomaly"

                    all_boxes.append({
                        "label": display_label,
                        "confidence": conf,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "anomaly" : is_anomaly,
                        "value" : final_value
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

# ----------------------------------------------------------
# 2) start_device_detector — Task 생성하지 말고 loop만 실행
# ----------------------------------------------------------
async def start_device_detector():
    try:
        await device_detector_loop()
    except asyncio.CancelledError:
        logger.info("[device_monitor] start_device_detector Cancelled")
        raise