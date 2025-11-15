# yolo_service/device_monitor.py

import asyncio
from loguru import logger

from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer
from ai_server.yolo_service.redis_frame_store import get_latest_frame
from ai_server.yolo_service.redis_client import save_device_result, get_device_state


YOLO_MODEL_PATH = "/app/ai_server/yolo_service/models/device_best.pt"
DETECTION_INTERVAL = 2.0

# 안정성 파라미터
CONF_THRESHOLD = 0.60               # YOLO 최소 confidence
STABLE_COUNT_REQUIRED = 2           # 동일 후보 라벨이 N번 연속 감지되면 변경

_device_loop_task: asyncio.Task | None = None
_device_model = None


async def device_detector_loop():
    """장비(AHU/Boiler/Chiller 등)를 2초마다 감지하는 메인 루프."""
    global _device_model

    logger.info("[device_monitor] 📡 디바이스 감지 루프 시작")

    # -----------------------
    # 1) Lazy load YOLO model
    # -----------------------
    if _device_model is None:
        try:
            logger.info("[device_monitor] YOLO 모델 로드 중...")
            _device_model = load_yolo_model(YOLO_MODEL_PATH)
            logger.info("[device_monitor] ✅ YOLO device 모델 로드 완료")
        except Exception as e:
            logger.exception(f"[device_monitor] ❌ YOLO 모델 로드 실패: {e}")
            return

    # -----------------------
    # 2) 상태 초기화
    # -----------------------
    prev_state = await get_device_state()   # Redis에서 가져온 이전 상태
    logger.debug(f"[device_monitor] Redis 저장 상태(prev_state): {prev_state}")
    
    candidate_label = None                  # 변경 후보 라벨
    stable_counter = 0                      # 후보 라벨의 안정성 카운터

    logger.info(f"[device_monitor] 초기 prev_state = {prev_state}")

    # -----------------------
    # 3) 감지 루프 시작
    # -----------------------
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

            logger.debug(f"[device_monitor] 감지: {label} ({confidence:.2f})")

            # -----------------------
            # (A) confidence 검사
            # -----------------------
            if confidence < CONF_THRESHOLD:
                logger.debug("[device_monitor] confidence 미달 → 안정성 초기화")
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # -----------------------
            # (B) 기존 상태와 같으면 안정화 리셋 (변경아님)
            # -----------------------
            if label == prev_state:
                candidate_label = None
                stable_counter = 0
                await asyncio.sleep(DETECTION_INTERVAL)
                continue

            # -----------------------
            # (C) 후보 라벨 안정화 체크
            # -----------------------
            if candidate_label != label:
                # 새로운 변화 후보 등장
                candidate_label = label
                stable_counter = 1
                logger.debug(f"[device_monitor] 후보 라벨 변경 → {candidate_label}")
            else:
                # 동일 후보 지속 감지
                stable_counter += 1
                logger.debug(
                    f"[device_monitor] 후보 안정화 진행 중 "
                    f"{candidate_label}: {stable_counter}/{STABLE_COUNT_REQUIRED}"
                )

            # -----------------------
            # (D) 변화 확정 (stable)
            # -----------------------
            if stable_counter >= STABLE_COUNT_REQUIRED:
                prev_state = candidate_label
                await save_device_result(prev_state, confidence)
                logger.info(f"[device_monitor] 🔄 상태 변경 확정 → {prev_state} ({confidence:.2f})")

                # reset
                candidate_label = None
                stable_counter = 0

        except asyncio.CancelledError:
            logger.info("[device_monitor] 🛑 디바이스 감지 루프 Cancelled")
            break

        except Exception as e:
            logger.exception(f"[device_monitor] 🚨 오류: {e}")

        await asyncio.sleep(DETECTION_INTERVAL)

    logger.info("[device_monitor] 디바이스 감지 루프 종료 완료")


async def start_device_detector():
    """device_detector_loop를 백그라운드 task로 시작"""
    global _device_loop_task

    if _device_loop_task and not _device_loop_task.done():
        logger.info("[device_monitor] 이미 실행 중 → start 무시")
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
        _device_loop_task = None
        logger.info("[device_monitor] 이미 종료됨")
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
    """현재 디바이스 감지 루프 실행 상태"""
    return _device_loop_task is not None and not _device_loop_task.done()
