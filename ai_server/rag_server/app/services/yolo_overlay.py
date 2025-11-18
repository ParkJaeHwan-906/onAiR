# app/services/yolo_overlay.py

import json
import redis.asyncio as redis

redis_client = redis.from_url("redis://redis:6379", decode_responses=False)
YOLO_RESULT_KEY = "cv:yolo:latest:result"


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
