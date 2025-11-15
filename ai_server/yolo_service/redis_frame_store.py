import redis.asyncio as redis
import cv2
import numpy as np


redis = redis.from_url("redis://localhost:6379", decode_responses=False)


async def get_latest_frame():
    data = await redis.get("cv:frame:latest")
    if not data:
        return None
    jpg = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
    return frame




async def get_cv_buffer_frames(n=20):
    frames = await redis.lrange("cv:frame:cv_buffer", -n, -1)
    result = []
    for b in frames:
        jpg = np.frombuffer(b, dtype=np.uint8)
        frame = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
        result.append(frame)
    return result



async def get_device_state() -> str | None:
    state = await redis.get("cv:state:device")
    if state is not None:
        return state.decode("utf-8") if isinstance(state, bytes) else state
    return None