import aioredis
import cv2
import numpy as np
from loguru import logger

# Redis 설정 (로컬 Redis 서버 기준)
redis = aioredis.from_url("redis://localhost:6379", decode_responses=False)

# Redis Key
REDIS_LATEST_FRAME_KEY = "cv:frame:latest"
REDIS_DEVICE_RESULT_KEY = "cv:result:device"


async def get_latest_frame() -> np.ndarray | None:
    data = await redis.get(REDIS_LATEST_FRAME_KEY)
    if not data:
        return None
    jpg = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
    return frame


async def store_device_result(result: dict) -> None:
    """
    YOLO device 결과를 Redis에 저장 (bytes 직렬화)
    """
    import pickle
    try:
        raw = pickle.dumps(result)
        await redis.set(REDIS_DEVICE_RESULT_KEY, raw)
        logger.info(f"[redis-store] device 결과 저장됨: {result}")
    except Exception as e:
        logger.error(f"[redis-store] device 결과 저장 실패: {e}")


async def get_device_result() -> dict | None:
    """
    Redis에서 device 결과 가져오기
    """
    import pickle
    raw = await redis.get(REDIS_DEVICE_RESULT_KEY)
    if not raw:
        return None
    try:
        return pickle.loads(raw)
    except Exception as e:
        logger.error(f"[redis-store] device 결과 불러오기 실패: {e}")
        return None