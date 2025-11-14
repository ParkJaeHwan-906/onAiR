# ai_server/yolo_service/redis_client.py

import asyncio
import json
import time
from typing import Optional, Any

import redis
from loguru import logger


class RedisClient:
    def __init__(
        self,
        host: str = "redis",
        port: int = 6379,
        db: int = 0,
        decode_responses: bool = False,
    ):
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=decode_responses,
                socket_timeout=3,
                socket_connect_timeout=3,
            )
            self.client.ping()
            logger.info("[RedisClient] Redis 연결 성공")
        except Exception as e:
            logger.error(f"[RedisClient] Redis 연결 실패: {e}")
            raise

    def get(self, key: str) -> Optional[Any]:
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"[RedisClient] get 실패 - key: {key}, error: {e}")
            return None

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        try:
            return self.client.set(name=key, value=value, ex=ex)
        except Exception as e:
            logger.error(f"[RedisClient] set 실패 - key: {key}, error: {e}")
            return False

    def delete(self, key: str) -> bool:
        try:
            return self.client.delete(key) > 0
        except Exception as e:
            logger.error(f"[RedisClient] delete 실패 - key: {key}, error: {e}")
            return False


# ---------------------------------------------------------
# 모듈 전역 싱글톤 및 공용 키
# ---------------------------------------------------------

_redis_client: Optional[RedisClient] = None

# 디바이스 상태 저장용 키
DEVICE_STATE_KEY = "cv:device_state"


def get_redis_client() -> RedisClient:
    """RedisClient 싱글톤 반환"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient(
            host="redis",
            port=6379,
            db=0,
            decode_responses=True,  # 문자열 JSON 저장용
        )
    return _redis_client


# ---------------------------------------------------------
# Device 상태 헬퍼 (run_device_detector, anomaly flow 에서 사용)
# ---------------------------------------------------------

async def save_device_result(label: str, confidence: float, ttl: int = 60) -> None:
    """
    디바이스 감지 결과를 Redis에 저장
    - label: AHU, Boiler, Chiller 등
    - confidence: 신뢰도
    """
    client = get_redis_client()
    payload = {
        "label": label,
        "confidence": float(confidence),
        "timestamp": time.time(),
    }
    data = json.dumps(payload)

    # sync redis 호출을 별도 스레드로 넘겨서 이벤트 루프 블로킹 방지
    await asyncio.to_thread(client.set, DEVICE_STATE_KEY, data, ttl)
    logger.debug(f"[RedisClient] 디바이스 상태 저장: {payload}")


async def get_device_state() -> Optional[str]:
    """
    Redis에 저장된 디바이스 상태(label) 조회
    - 저장값 없으면 None 반환
    """
    client = get_redis_client()
    raw = await asyncio.to_thread(client.get, DEVICE_STATE_KEY)

    if raw is None:
        return None

    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except Exception:
            logger.warning("[RedisClient] 디바이스 상태 디코딩 실패")
            return None

    try:
        data = json.loads(raw)
        label = data.get("label")
        return label
    except Exception as e:
        logger.error(f"[RedisClient] 디바이스 상태 파싱 실패: {e}")
        return None


async def clear_device_state() -> None:
    """디바이스 상태 초기화"""
    client = get_redis_client()
    await asyncio.to_thread(client.delete, DEVICE_STATE_KEY)
    logger.debug("[RedisClient] 디바이스 상태 초기화 완료")
