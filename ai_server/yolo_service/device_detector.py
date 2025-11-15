# yolo_service/device_monitor.py

import asyncio
from loguru import logger

from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer
from ai_server.yolo_service.redis_frame_store import get_latest_frame
from ai_server.yolo_service.redis_client import save_device_result, get_device_state


YOLO_MODEL_PATH = "/app/ai_server/yolo_service/models/device_best.pt"
DETECTION_INTERVAL = 2.0

# 안정성 강화 파라미터
CONF_THRESHOLD = 0.60             # 최소 confidence
STABLE_COUNT_REQUIRED = 2        # 연속 N번 같은 라벨일 때만 수정

# 내부 Task
_device_loop_task: asyncio.Task | None = None
_device_model = None


async def device_detector_loop():
    """장비(AHU/Boiler/Chiller 등)를 지속 감지하는 메인 루프."""
    global _device_model
    logger.info("[device_monitor] 📡 디바이스 감지 루프 시작")

    # YOLO 모델 Lazy Load
    if _device_model is None:
        try:
            logger.info("[device_monitor] YOLO 모델 로드 중...")
            _device_model = load_yolo_model(YOLO_MODEL_PATH)
            logger.info("[device_monitor] ✅ YOLO device 모델 로드 완료")
        except Exception as e:
            logger.exception(f"[device_monitor] ❌ YOLO 모델 로드 실패: {e}")
            return

    prev_state = await get_device_state()   # Redis에 저장된 이전 상태
    stable_counter = 0                      # 연속 동일 감지 횟수
    candidate_label = None                  # 후보 라벨

    while True:
        try:
            frame = await get_latest_frame()

            if frame is None:
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            detections = yolo_infer(_device_model, frame, return_boxes=False)

            if not detections:
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # top-1 detection
            top = max(detections, key=lambda d: d["confidence"])
            label, confidence = top["label"], top["confidence"]
            logger.debug(f"[device_monitor] 감지된 디바이스: {label} ({confidence:.2f})")

            # 1) confidence threshold 검사
            if confidence < CONF_THRESHOLD:
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # 2) 안정성 검증 (hysteresis)
            if label == prev_state:
                stable_counter += 1
            else:
                candidate_label = label
                stable_counter = 1

            # 3) stable_count 만족 시 업데이트
            if stable_counter >= STABLE_COUNT_REQUIRED and label != prev_state:
                await save_device_result(label, confidence)
                prev_state = label
                logger.info(f"[device_monitor] 🔄 상태 변경: {label} ({confidence:.2f})")

        except asyncio.CancelledError:
            logger.info("[device_monitor] 🛑 디바이스 감지 루프 중단됨")
            break

        except Exception as e:
            logger.exception(f"[device_monitor] 🚨 감지 중 오류 발생: {e}")

        await asyncio.sleep(DETECTION_INTERVAL)

    logger.info("[device_monitor] 디바이스 감지 루프 종료 완료")


async def start_device_detector():
    """device_detector_loop를 백그라운드로 시작"""
    global _device_loop_task

    if _device_loop_task and not _device_loop_task.done():
        logger.info("[device_monitor] 이미 실행 중 — start 무시")
        return

    loop = asyncio.get_running_loop()
    _device_loop_task = loop.create_task(device_detector_loop())
    logger.info("[device_monitor] ▶ device_detector_loop STARTED")


async def stop_device_detector():
    """device_detector_loop 중단"""
    global _device_loop_task

    if not _device_loop_task:
        logger.info("[device_monitor] 중단할 루프 없음")
        return

    if _device_loop_task.done():
        logger.info("[device_monitor] 루프는 이미 종료됨")
        _device_loop_task = None
        return

    logger.info("[device_monitor] ⏹ 디바이스 감지 루프 중단 요청")
    _device_loop_task.cancel()

    try:
        await _device_loop_task
    except asyncio.CancelledError:
        logger.info("[device_monitor] CancelledError 정상 처리")

    _device_loop_task = None
    logger.info("[device_monitor] 🛑 device_detector_loop STOPPED")


def is_device_detector_running() -> bool:
    """현재 디바이스 감지 루프 실행 여부"""
    return _device_loop_task is not None and not _device_loop_task.done()
