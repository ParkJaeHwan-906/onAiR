# app/services/yolo_overlay.py

import json
import redis.asyncio as redis

redis_client = redis.from_url("redis://redis:6379", decode_responses=False)

YOLO_RESULT_KEY = "cv:yolo:latest:result"

async def get_latest_yolo_result():
    data = await redis_client.get(YOLO_RESULT_KEY)
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None
