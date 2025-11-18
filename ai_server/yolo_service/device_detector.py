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

    # 2) Redis 상태 초기화
    info = await get_device_state()
    prev_state = info["label"] if info else None
    candidate_label = None
    stable_counter = 0

    logger.info(f"[device_monitor] 초기 prev_state = {prev_state}")

    # 3) 감지 루프
    while True:
        try:
            frame, ts = await get_latest_frame()
            logger.info(f"[device_monitor] Redis 저장 상태(prev_state): {prev_state}")

            if frame is None:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # YOLO 추론
            detections = yolo_infer(_device_model, frame, return_boxes=False)

            # ─────────────────────────────
            # (A) 모든 박스 저장용 리스트
            # ─────────────────────────────
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

            # 오버레이 저장 (전체 박스)
            try:
                await save_yolo_result(ts, all_boxes)
                logger.debug("[device_monitor] 📤 ALL YOLO 박스 Redis 저장 완료")
            except Exception as e:
                logger.exception(f"[device_monitor] overlay 저장 오류: {e}")

            # ─────────────────────────────
            # (B) 디바이스 상태 감지만 DEVICE_CLASSES 필터
            # ─────────────────────────────
            device_candidates = [
                d for d in detections
                if d["label"] in DEVICE_CLASSES and d["confidence"] >= CONF_THRESHOLD
            ]

            # 감지 없음
            if not device_candidates:
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # 최고 confidence 디바이스
            top = max(device_candidates, key=lambda d: d["confidence"])
            label, confidence = top["label"], top["confidence"]
            logger.debug(f"[device_monitor] 감지: {label} ({confidence:.2f})")

            # confidence 기준 미달
            if confidence < CONF_THRESHOLD:
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # 기존 상태와 같으면 안정화 초기화
            if label == prev_state:
                candidate_label = None
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # 라벨 변경
            if candidate_label != label:
                candidate_label = label
                stable_counter = 1
                logger.debug(f"[device_monitor] 후보 라벨 변경 → {candidate_label}")
            else:
                stable_counter += 1
                logger.debug(
                    f"[device_monitor] 후보 안정화 진행 {candidate_label}: "
                    f"{stable_counter}/{STABLE_COUNT_REQUIRED}"
                )

            # 안정화 완료 → 저장
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
    """main.py에서 Task로 실행할 엔트리 포인트.
    Task는 main.py가 관리.
    """
    try:
        await device_detector_loop()
    except asyncio.CancelledError:
        logger.info("[device_monitor] start_device_detector Cancelled")
        raise

