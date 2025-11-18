# ai_server/rag_server/services/frame_collector.py

import redis.asyncio as redis
import cv2
import numpy as np
import time

redis_client = redis.from_url("redis://redis:6379", decode_responses=False)

LATEST_FRAME_KEY = "cv:frame:latest:jpg"
LATEST_TS_KEY    = "cv:frame:latest:ts"
FRAME_BUFFER_KEY = "cv:frame:buffer:jpg"
TS_BUFFER_KEY     = "cv:frame:buffer:ts"

BUFFER_SIZE = 30


async def add_frame(frame, timestamp=None):
    if timestamp is None:
        timestamp = int(time.time() * 1000)

    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        return False

    jpg = encoded.tobytes()

    # latest
    await redis_client.set(LATEST_FRAME_KEY, jpg)
    await redis_client.set(LATEST_TS_KEY, str(timestamp))

    # buffer
    await redis_client.rpush(FRAME_BUFFER_KEY, jpg)
    await redis_client.rpush(TS_BUFFER_KEY, str(timestamp))

    await redis_client.ltrim(FRAME_BUFFER_KEY, -BUFFER_SIZE, -1)
    await redis_client.ltrim(TS_BUFFER_KEY, -BUFFER_SIZE, -1)

    return True



async def get_latest_frame():
    # 최신 프레임 + TS 둘 다 가져옴
    jpg = await redis_client.get(LATEST_FRAME_KEY)
    ts  = await redis_client.get(LATEST_TS_KEY)

    if jpg is None or ts is None:
        return None, None

    jpg_np = np.frombuffer(jpg, dtype=np.uint8)
    frame = cv2.imdecode(jpg_np, cv2.IMREAD_COLOR)
    timestamp = int(ts)

    return frame, timestamp
