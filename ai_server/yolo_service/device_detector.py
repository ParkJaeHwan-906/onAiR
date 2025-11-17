# yolo_service/device_detector.py


import asyncio
from loguru import logger

from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer
from ai_server.yolo_service.redis_client import (
    save_device_state,
    get_device_state,
    get_latest_frame
)

YOLO_MODEL_PATH = "/app/ai_server/yolo_service/models/device_best.pt"

CONF_THRESHOLD = 0.65
STABLE_COUNT_REQUIRED = 2

_device_model = None


async def device_detector_loop():
    """13fps 스트림 중 절반 프레임(≈6~7fps) YOLO 감지 루프"""

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

    frame_count = 0
    # 3) 프레임 기반 감지 루프
    while True:
        try:
            frame = await get_latest_frame()

            if frame is None:
                await asyncio.sleep(0.01)
                continue

            frame_count += 1

            # -----------------------------------------------------
            # YOLO 실행: 13fps → 절반 프레임(≈6.5fps) 처리
            # -----------------------------------------------------
            if frame_count % 2 != 0:
                continue  # skip half the frames

            detections = yolo_infer(_device_model, frame, return_boxes=False)

            if not detections:
                stable_counter = 0
                continue

            # 가장 높은 confidence 선택
            top = max(detections, key=lambda d: d["confidence"])
            label, confidence = top["label"], top["confidence"]

            logger.debug(f"[device_monitor] 감지: {label} ({confidence:.2f})")

            # confidence 기준 미달
            if confidence < CONF_THRESHOLD:
                stable_counter = 0
                continue

            # 기존 상태와 같으면 안정화 초기화
            if label == prev_state:
                candidate_label = None
                stable_counter = 0
                continue

            # 후보 라벨 안정화
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

            # 안정성 조건 만족 → 상태 업데이트
            if stable_counter >= STABLE_COUNT_REQUIRED:
                prev_state = candidate_label
                await save_device_state(prev_state, confidence)
                logger.info(
                    f"[device_monitor] 🔄 상태 변경 확정 → {prev_state} ({confidence:.2f})"
                )

                candidate_label = None
                stable_counter = 0

        except asyncio.CancelledError:
            logger.info("[device_monitor] 🛑 디바이스 감지 루프 Cancelled")
            break

        except Exception as e:
            logger.exception(f"[device_monitor] 🚨 오류: {e}")
            continue

    logger.info("[device_monitor] 디바이스 감지 루프 종료 완료")



# 2) start_device_detector — Task 생성하지 말고 loop만 실행
async def start_device_detector():
    """main.py에서 Task로 실행할 엔트리 포인트.
    Task는 main.py가 관리.
    """
    try:
        await device_detector_loop()
    except asyncio.CancelledError:
        logger.info("[device_monitor] start_device_detector Cancelled")
        raise

