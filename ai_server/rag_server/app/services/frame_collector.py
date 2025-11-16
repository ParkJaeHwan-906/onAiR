# ai_server/yolo_service/frame_collector.py

import redis.asyncio as redis
import cv2
import numpy as np

redis_client = redis.from_url("redis://redis:6379", decode_responses=False)

LATEST_FRAME_KEY = "cv:frame:latest"
FRAME_BUFFER_KEY = "cv:frame:cv_buffer"

async def add_frame(frame):
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        return False

    jpg = encoded.tobytes()

    await redis_client.set(LATEST_FRAME_KEY, jpg)
    await redis_client.rpush(FRAME_BUFFER_KEY, jpg)
    await redis_client.ltrim(FRAME_BUFFER_KEY, -30, -1)

    return True

async def get_latest_frame():
    data = await redis_client.get(LATEST_FRAME_KEY)
    if not data:
        return None

    jpg = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(jpg, cv2.IMREAD_COLOR)
