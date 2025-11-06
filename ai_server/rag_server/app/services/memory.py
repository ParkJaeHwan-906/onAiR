from __future__ import annotations
from typing import Any, List, Dict
import json

import redis
from app.core.config import settings


_redis: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _key(session_id: str) -> str:
    return f"{settings.REDIS_PREFIX}:session:{session_id}"


def append_event(session_id: str, event: Dict[str, Any]) -> None:
    """
    Append an event to the conversation history list for the given session.
    Event example: {"role": "user|system|assistant", "type": "clarify|answer|evidence", "data": {...}}
    """
    r = _get_client()
    r.rpush(_key(session_id), json.dumps(event, ensure_ascii=False))


def get_history(session_id: str, limit: int | None = 20) -> List[Dict[str, Any]]:
    r = _get_client()
    items = r.lrange(_key(session_id), -limit, -1) if limit else r.lrange(_key(session_id), 0, -1)
    history: List[Dict[str, Any]] = []
    for it in items:
        try:
            history.append(json.loads(it))
        except Exception:
            continue
    return history


def clear_history(session_id: str) -> None:
    r = _get_client()
    r.delete(_key(session_id))


