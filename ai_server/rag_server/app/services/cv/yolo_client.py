from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional

import aiohttp
import cv2
import numpy as np
from loguru import logger

YOLO_SERVICE_URL = os.getenv("YOLO_SERVICE_URL", "http://localhost:9000")
YOLO_TIMEOUT = 5.0

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


@dataclass
class YOLOServiceError(Exception):
    code: str
    message: str
    detail: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {"code": self.code, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return payload


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is not None and not _session.closed:
        return _session

    async with _session_lock:
        if _session is None or _session.closed:
            timeout = aiohttp.ClientTimeout(total=YOLO_TIMEOUT)
            _session = aiohttp.ClientSession(timeout=timeout)
    return _session


async def close_session() -> None:
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None


def _encode_frame(frame: np.ndarray) -> bytes:
    success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not success:
        raise ValueError("프레임 JPEG 인코딩 실패")
    return buffer.tobytes()


async def _post_form(
    path: str,
    files: List[bytes],
    filenames: Optional[List[str]] = None,
) -> Dict[str, Any]:
    url = f"{YOLO_SERVICE_URL.rstrip('/')}{path}"
    session = await _get_session()

    data = aiohttp.FormData()
    for idx, content in enumerate(files):
        filename = filenames[idx] if filenames and idx < len(filenames) else f"frame_{idx}.jpg"
        data.add_field("file", content, filename=filename, content_type="image/jpeg")

    try:
        async with session.post(url, data=data) as resp:
            payload = await resp.json(content_type=None)
            if resp.status >= 400 or not payload.get("success"):
                error = payload.get("error", {})
                raise YOLOServiceError(
                    code=error.get("code", "YOLO_INFERENCE_ERROR"),
                    message=error.get("message", "YOLO 서비스 오류"),
                    detail=error.get("detail"),
                )
            return payload.get("data", {})
    except asyncio.TimeoutError as exc:
        raise YOLOServiceError("YOLO_TIMEOUT", "YOLO 서비스 응답 지연", {"path": path}) from exc
    except YOLOServiceError:
        raise
    except Exception as exc:
        logger.exception(f"[yolo-client] YOLO 서비스 호출 오류: {exc}")
        raise YOLOServiceError("YOLO_REQUEST_ERROR", "YOLO 서비스 호출 실패", {"path": path}) from exc


async def infer_device(frame: np.ndarray) -> Dict[str, Any]:
    jpeg = _encode_frame(frame)
    data = await _post_form("/infer/device", [jpeg])
    return data


async def infer_module(frames: List[np.ndarray]) -> Dict[str, Any]:
    if not frames:
        return {"frames": [], "top_detections": []}
    files = [_encode_frame(f) for f in frames]
    data = await _post_form("/infer/module", files)
    return data


async def infer_panel(frame: np.ndarray) -> Dict[str, Any]:
    jpeg = _encode_frame(frame)
    data = await _post_form("/infer/panel", [jpeg])
    return data


async def get_health() -> Dict[str, Any]:
    url = f"{YOLO_SERVICE_URL.rstrip('/')}/health"
    session = await _get_session()
    try:
        async with session.get(url) as resp:
            return await resp.json(content_type=None)
    except Exception as exc:
        logger.exception(f"[yolo-client] YOLO 헬스체크 실패: {exc}")
        raise YOLOServiceError("YOLO_HEALTH_ERROR", "YOLO 헬스체크 실패") from exc

