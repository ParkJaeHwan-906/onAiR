
# app/services/cv/redis_utils.py
import aioredis, base64, numpy as np, cv2, json, asyncio

async def get_redis():
    return await aioredis.from_url("redis://redis:6379", decode_responses=True)

async def save_frame(redis, frame, ttl=10):
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok: return
    b64 = base64.b64encode(buf).decode()
    await redis.set("cv:frame:latest", b64, ex=ttl)

async def load_frame(redis):
    b64 = await redis.get("cv:frame:latest")
    if not b64: return None
    arr = np.frombuffer(base64.b64decode(b64), np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

async def set_json(redis, key, obj, ttl=None):
    s = json.dumps(obj)
    if ttl: await redis.set(key, s, ex=ttl)
    else: await redis.set(key, s)

async def get_json(redis, key):
    s = await redis.get(key)
    return json.loads(s) if s else None