# yolo_service/device_detector.py

import asyncio
from loguru import logger
from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer
from ai_server.yolo_service.redis_client import save_device_state, get_device_state, get_latest_frame, save_yolo_result
import time


YOLO_MODEL_PATH = "/app/ai_server/yolo_service/models/device_best.pt"
DETECTION_INTERVAL = 2.0

# 안정성 파라미터
CONF_THRESHOLD = 0.7
STABLE_COUNT_REQUIRED = 3

# 모델 및 Task (Task는 main.py가 가지고 있음)
_device_model = None

# ----------------------------------------------------------
# 1) 메인 디바이스 감지 루프 (cancel 대응 완료)
# ----------------------------------------------------------
async def device_detector_loop():
    """장비(AHU/Boiler/Chiller 등)를 2초마다 감지하는 메인 루프."""

    global _device_model
    logger.info("[device_monitor] 📡 디바이스 감지 루프 시작")

    # 1) YOLO 모델 로드
    if _device_model is None:
        try:
            logger.info("[device_monitor] YOLO 모델 로드 중...")
            _device_model = load_yolo_model(YOLO_MODEL_PATH)
            logger.info("[device_monitor] ✅ YOLO device 모델 로드 완료")
        except Exception as e:
            logger.exception(f"[device_monitor] ❌ YOLO 모델 로드 실패: {e}")
            return

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

            detections = yolo_infer(_device_model, frame, return_boxes=False)

            if not detections:
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            top = max(detections, key=lambda d: d["confidence"])
            label, confidence = top["label"], top["confidence"]

            if(confidence > 0.75):
                try:
                    box = top["box"]
                    save_yolo_result(ts, prev_state, confidence, box)
                    logger.debug("[device_monitor] 📤 overlay 결과 Redis 저장 완료")
                except Exception as e:
                    logger.exception(f"[device_monitor] overlay 저장 오류: {e}")

            logger.debug(f"[device_monitor] 감지: {label} ({confidence:.2f})")

            # confidence 기준 미달
            if confidence < CONF_THRESHOLD:
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # 기존 상태와 같으면 후보 초기화
            if label == prev_state:
                candidate_label = None
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue


            # 후보 라벨 안정화 검사
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

            # 안정성 만족 시 prev_state 업데이트
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

