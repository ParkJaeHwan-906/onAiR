"""
기기 타입 모니터 (YOLO 서비스 연동)
- 백그라운드에서 최신 프레임 1장만 가져와서 YOLO 서비스 호출
- 프레임은 저장하지 않고 버림
- 탐지된 장비 타입만 전역변수(current_device_type)에 저장
"""

import asyncio

from loguru import logger

from app.services.cv.frame_collector import collect_latest_n_frames
from app.services.cv.yolo_client import YOLOServiceError, infer_device
from app.services.cv.utils import select_sharpest_frame

# 현재 감지된 장비 타입 (다른 서비스에서 참조)
current_device_type: str = "unknown"


async def background_device_detector():
    """
    백그라운드에서 주기적으로 프레임 스트림의 최신 프레임 1장을 가져와 장비 타입 탐지
    - 프레임은 저장하지 않고 버림
    - 탐지된 장비 타입만 전역변수에 저장
    """
    global current_device_type

    logger.info("✅ [device_monitor] 장비 모니터링 시작됨 (주기: 2초)")

    while True:
        try:
            frames = await collect_latest_n_frames(n=3)
            if not frames:
                await asyncio.sleep(2)
                continue

            frames_to_use = frames[-3:] if len(frames) >= 3 else frames
            latest_frame = select_sharpest_frame(frames_to_use)

            try:
                response = await infer_device(latest_frame)
            except YOLOServiceError as err:
                logger.warning(
                    "[device_monitor] YOLO 서비스 호출 실패 (code=%s, msg=%s)",
                    err.code,
                    err.message,
                )
            else:
                device_label = response.get("label")
                if device_label:
                    current_device_type = device_label
                    logger.info("🔍 [device_monitor] 감지된 장비: %s", device_label)
                else:
                    logger.debug("[device_monitor] 장비 탐지 실패, 이전 상태 유지")

        except Exception as exc:  # pragma: no cover
            logger.exception("❌ [device_monitor] 루프 오류: %s", exc)

        await asyncio.sleep(2)
