import redis.asyncio as redis
import cv2
import numpy as np
import asyncio
import json
from datetime import datetime

# Redis 연결
redis = redis.from_url("redis://redis:6379/0", decode_responses=False)

# 전역 상태
_cv_collection_active = False
_cv_collection_lock = asyncio.Lock()


# ========== [ 프레임 관련 기능 ] ==========

async def add_frame(frame: np.ndarray):
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        return False
    jpg_bytes = encoded.tobytes()

    # 최신 프레임 저장
    await redis.set("cv:frame:latest", jpg_bytes)

    # 수집 활성화된 경우만 버퍼에 추가
    if _cv_collection_active:
        await redis.rpush("cv:frame:cv_buffer", jpg_bytes)
        await redis.ltrim("cv:frame:cv_buffer", -30, -1)
    return True


async def get_latest_frame() -> np.ndarray | None:
    data = await redis.get("cv:frame:latest")
    if not data:
        return None
    return _decode_jpeg(data)


async def get_cv_buffer_frames(n: int = 10) -> list[np.ndarray]:
    data_list = await redis.lrange("cv:frame:cv_buffer", -n, -1)
    return [_decode_jpeg(data) for data in data_list if data]


def _decode_jpeg(data: bytes) -> np.ndarray | None:
    np_arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)


async def start_cv_collection():
    global _cv_collection_active
    async with _cv_collection_lock:
        _cv_collection_active = True


async def stop_cv_collection():
    global _cv_collection_active
    async with _cv_collection_lock:
        _cv_collection_active = False
        await redis.delete("cv:frame:cv_buffer")


async def get_device_result() -> dict | None:
    raw = await redis.get("cv:result:device")
    if raw is None:
        return None
    return json.loads(raw)


async def get_device_state() -> str | None:
    state = await redis.get("cv:state:device")
    if state is not None:
        return state.decode("utf-8") if isinstance(state, bytes) else state
    return None


async def reset_device_state():
    await redis.delete("cv:state:device")
