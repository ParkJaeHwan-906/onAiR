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
LATEST_FRAME_KEY = "cv:frame:latest:jpg"
LATEST_TS_KEY    = "cv:frame:latest:ts"
FRAME_BUFFER_KEY = "cv:frame:buffer:jpg"
TS_BUFFER_KEY    = "cv:frame:buffer:ts"
YOLO_RESULT_KEY = "cv:yolo:latest:result"

BUFFER_SIZE = 30

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

async def save_yolo_result(ts, label, confidence, box):
    data = {
        "frame_ts": ts,
        "boxes": [
            {
                "label": label,
                "confidence": float(confidence),
                "x1": int(box["x1"]),
                "y1": int(box["y1"]),
                "x2": int(box["x2"]),
                "y2": int(box["y2"]),
            }
        ],
        "status": "ok",
        "updated_at": int(time.time() * 1000)
    }
    await redis_client.set(YOLO_RESULT_KEY, json.dumps(data))

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


