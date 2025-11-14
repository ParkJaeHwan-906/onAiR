import asyncio
from typing import Optional
import aioredis

# Redis 키 설정
REDIS_KEY_DEVICE_RESULT = "cv:result:device"

# 전역 상태 캐시
_cached_result: Optional[dict] = None
_result_lock = asyncio.Lock()

# Redis 클라이언트
redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)


async def save_device_result(result: dict) -> None:
    """
    YOLO device 결과를 Redis와 전역 변수에 저장
    """
    global _cached_result
    async with _result_lock:
        _cached_result = result
        await redis.set(REDIS_KEY_DEVICE_RESULT, str(result))


async def get_device_result_from_redis() -> Optional[dict]:
    """
    Redis에서 device 결과 가져오기 (전역 캐시 사용 안함)
    """
    raw = await redis.get(REDIS_KEY_DEVICE_RESULT)
    if not raw:
        return None
    try:
        return eval(raw)  # 안전을 위해 나중에 JSON 사용 고려
    except Exception:
        return None


async def get_latest_device_result() -> Optional[dict]:
    """
    전역 변수에서 가장 최신 device 결과 반환 (속도 ↑)
    """
    async with _result_lock:
        return _cached_result
