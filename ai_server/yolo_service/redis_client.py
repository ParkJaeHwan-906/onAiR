# ai_server/yolo_service/redis_client.py

import json
import time
import asyncio
import redis.asyncio as redis
import numpy as np
import cv2

# Redis 연결(비동기)
redis_client = redis.from_url("redis://redis:6379", decode_responses=False)

# 통합 Redis Key
DEVICE_STATE_KEY = "cv:state:device"
LATEST_FRAME_KEY = "cv:frame:latest"
FRAME_BUFFER_KEY = "cv:frame:cv_buffer"

# ---------------------------
# Device State 저장/조회
# ---------------------------

async def save_device_state(label: str, confidence: float):
    data = {
        "label": label,
        "confidence": float(confidence),
        "timestamp": time.time()
    }
    await redis_client.set(DEVICE_STATE_KEY, json.dumps(data))

async def get_device_state() -> dict | None:
    raw = await redis_client.get(DEVICE_STATE_KEY)
    if not raw:
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except:
        return None


# ---------------------------
# Frame Read-only (YOLO용)
# ---------------------------

async def get_latest_frame():
    data = await redis_client.get(LATEST_FRAME_KEY)
    if not data:
        return None

    jpg = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(jpg, cv2.IMREAD_COLOR)


async def get_cv_buffer_frames(n=30):
    frames = await redis_client.lrange(FRAME_BUFFER_KEY, -n, -1)
    result = []
    for b in frames:
        jpg = np.frombuffer(b, dtype=np.uint8)
        frame = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
        if frame is not None:
            result.append(frame)
    return result