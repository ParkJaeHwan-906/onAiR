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

async def save_yolo_result(frame_ts: int, boxes: list):
    try:
        payload = {
            "frame_ts": frame_ts,
            "boxes": boxes,                   # 여러 박스 저장
            "status": "ok",
            "updated_at": int(time.time() * 1000),
        }

        await redis_client.set(YOLO_RESULT_KEY, json.dumps(payload))

    except Exception as e:
        return None

# ---------------------------
# Frame Read-only (YOLO용)
# ---------------------------

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



async def get_cv_buffer_frames(n=30):
    frames = await redis_client.lrange(FRAME_BUFFER_KEY, -n, -1)
    result = []
    for b in frames:
        jpg = np.frombuffer(b, dtype=np.uint8)
        frame = cv2.imdecode(jpg, cv2.IMREAD_COLOR)
        if frame is not None:
            result.append(frame)
    return result


async def get_latest_yolo_result():
    """
    Redis에 저장된 YOLO 결과(JSON)를 그대로 반환한다.
    frame_ts, boxes, status만 그대로 프론트에 전달한다.
    """

    data = await redis_client.get(YOLO_RESULT_KEY)
    if not data:
        return None

    try:
        raw = json.loads(data)
    except Exception:
        return None

    # --- 여기서 정합성 유지용 필드만 추출 ---
    result = {
        "frame_ts": raw.get("frame_ts"),
        "boxes": raw.get("boxes", []),
        "status": raw.get("status", "ok"),
        "updated_at" : raw.get("updated_at", None)
    }

    return result
