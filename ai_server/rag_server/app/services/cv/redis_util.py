
# app/services/cv/redis_utils.py
from redis.asyncio import Redis
import base64, numpy as np, cv2, json, asyncio
from typing import List, Optional

# Sliding window 크기 (20프레임)
SLIDING_WINDOW_SIZE = 20

async def get_redis():
    return Redis.from_url("redis://redis:6379", decode_responses=False)

async def save_frame(redis, frame, ttl=10):
    """단일 프레임을 Redis에 저장 (최신 프레임)"""
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok: return
    b64 = base64.b64encode(buf).decode()
    await redis.set("cv:frame:latest", b64, ex=ttl)

async def save_frame_to_sliding_window(redis, frame, ttl=30):
    """
    프레임을 sliding window 형식으로 Redis에 저장 (최대 20프레임)
    - cv:frames:0 ~ cv:frames:19 형태로 저장
    - 새로운 프레임이 들어오면 가장 오래된 프레임을 덮어씀
    """
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok: return
    
    b64 = base64.b64encode(buf).decode()
    
    # 현재 인덱스 가져오기 (없으면 0부터 시작)
    current_idx_str = await redis.get("cv:frames:index")
    current_idx = int(current_idx_str) if current_idx_str else 0
    
    # 프레임 저장
    await redis.set(f"cv:frames:{current_idx}", b64, ex=ttl)
    
    # 인덱스 업데이트 (순환)
    next_idx = (current_idx + 1) % SLIDING_WINDOW_SIZE
    await redis.set("cv:frames:index", str(next_idx), ex=ttl)
    
    # 총 프레임 수 업데이트 (최대 20)
    frame_count = await redis.get("cv:frames:count")
    if frame_count:
        count = int(frame_count)
        if count < SLIDING_WINDOW_SIZE:
            await redis.incr("cv:frames:count")
    else:
        await redis.set("cv:frames:count", "1", ex=ttl)

async def get_latest_frames(redis=None, limit: int = 20) -> List[np.ndarray]:
    """
    Redis에서 최근 프레임들을 가져옴 (sliding window)
    Args:
        redis: Redis 클라이언트 (None이면 새로 생성)
        limit: 가져올 최대 프레임 수 (기본값 20)
    Returns:
        프레임 리스트 (최신 순서)
    """
    if redis is None:
        redis = await get_redis()
    
    frames = []
    frame_count_str = await redis.get("cv:frames:count")
    if not frame_count_str:
        return frames
    
    frame_count = int(frame_count_str)
    current_idx_str = await redis.get("cv:frames:index")
    current_idx = int(current_idx_str) if current_idx_str else 0
    
    # 실제 저장된 프레임 수만큼만 가져오기
    actual_count = min(frame_count, SLIDING_WINDOW_SIZE, limit)
    
    # 최신 프레임부터 역순으로 가져오기
    for i in range(actual_count):
        idx = (current_idx - 1 - i) % SLIDING_WINDOW_SIZE
        b64 = await redis.get(f"cv:frames:{idx}")
        if b64:
            try:
                if isinstance(b64, bytes):
                    b64 = b64.decode()
                arr = np.frombuffer(base64.b64decode(b64), np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    frames.append(frame)
            except Exception as e:
                print(f"⚠️ 프레임 디코딩 오류 (idx={idx}): {e}")
                continue
    
    return frames

async def load_frame(redis):
    """최신 단일 프레임 로드"""
    b64 = await redis.get("cv:frame:latest")
    if not b64: return None
    if isinstance(b64, bytes):
        b64 = b64.decode()
    arr = np.frombuffer(base64.b64decode(b64), np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

async def set_json(redis, key, obj, ttl=None):
    s = json.dumps(obj)
    if ttl: await redis.set(key, s, ex=ttl)
    else: await redis.set(key, s)

async def get_json(redis, key):
    s = await redis.get(key)
    if s is None:
        return None
    if isinstance(s, bytes):
        s = s.decode()
    return json.loads(s)