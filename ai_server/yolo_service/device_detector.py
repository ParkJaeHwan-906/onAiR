# yolo_service/device_detector.py

import asyncio
from loguru import logger
from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer
from ai_server.yolo_service.redis_client import save_device_state, get_device_state, get_latest_frame, save_yolo_result
from ai_server.yolo_service.config_all_model import ALL_MODEL_PATH, DEVICE_CLASSES
import time

DETECTION_INTERVAL = 2.0

# 안정성 파라미터
CONF_THRESHOLD = 0.75
STABLE_COUNT_REQUIRED = 5

_device_model = None
# ----------------------------------------------------------
# 1) 메인 디바이스 감지 루프 (cancel 대응 완료)
# ----------------------------------------------------------
async def device_detector_loop():
    global _device_model
    _device_model = load_yolo_model(ALL_MODEL_PATH)
    logger.info("[device_monitor] 📡 디바이스 감지 루프 시작")

    info = await get_device_state()
    prev_state = info["label"] if info else None
    candidate_label = None
    stable_counter = 0

    logger.info(f"[device_monitor] 초기 prev_state = {prev_state}")

    while True:
        try:
            # --- 1) 최신 프레임 읽기 ---
            res = await get_latest_frame()
            if not res:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # res가 tuple인지 dict인지 안전하게 처리
            if isinstance(res, tuple):
                frame, ts = res
            elif isinstance(res, dict):
                frame = res.get("frame")
                ts = res.get("ts") or res.get("timestamp")
            else:
                logger.warning("[device_monitor] 잘못된 frame 포맷")
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            if frame is None:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            logger.info(f"[device_monitor] Redis 저장 상태(prev_state): {prev_state}")

            # --- 2) YOLO 추론 ---
            detections = yolo_infer(_device_model, frame, return_boxes=True)

            # --- 3) 모든 박스 Redis 저장 ---
            all_boxes = []
            for d in detections:
                b = d["box"]
                all_boxes.append({
                    "label": d["label"],
                    "confidence": float(d["confidence"]),
                    "x1": int(b[0]),
                    "y1": int(b[1]),
                    "x2": int(b[2]),
                    "y2": int(b[3]),
                })

            try:
                await save_yolo_result(ts, all_boxes)
                logger.debug("[device_monitor] 📤 ALL YOLO 박스 Redis 저장 완료")
            except Exception as e:
                logger.exception(f"[device_monitor] overlay 저장 오류: {e}")

            # --- 4) 디바이스 후보 필터링 ---
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
            logger.debug(f"[device_monitor] 감지: {label} ({confidence:.2f})")

            if confidence < CONF_THRESHOLD:
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # --- 5) 안정화 로직 ---
            if label == prev_state:
                candidate_label = None
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            if candidate_label != label:
                candidate_label = label
                stable_counter = 1
                logger.debug(f"[device_monitor] 후보 라벨 변경 → {candidate_label}")
            else:
                stable_counter += 1
                logger.debug(f"[device_monitor] 안정화 {candidate_label}: {stable_counter}/{STABLE_COUNT_REQUIRED}")

            if stable_counter >= STABLE_COUNT_REQUIRED:
                prev_state = candidate_label
                await save_device_state(prev_state, confidence)
                logger.info(f"[device_monitor] 🔄 상태 변경 확정 → {prev_state} ({confidence:.2f})")
                candidate_label = None
                stable_counter = 0

        except asyncio.CancelledError:
            logger.info("[device_monitor] 🛑 디바이스 감지 루프 Cancelled")
            break

        except Exception as e:
            logger.exception(f"[device_monitor] 🚨 오류: {e}")

        await asyncio.sleep(DETECTION_INTERVAL)

    logger.info("[device_monitor] 디바이스 감지 루프 종료 완료")




# ----------------------------------------------------------
# 2) start_device_detector — Task 생성하지 말고 loop만 실행
# ----------------------------------------------------------
async def start_device_detector():
    try:
        await device_detector_loop()
    except asyncio.CancelledError:
        logger.info("[device_monitor] start_device_detector Cancelled")
        raise

