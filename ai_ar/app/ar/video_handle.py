from app.sockets.socket_manager import sio
import numpy as np
import cv2
import base64

_MAX_BYTES = 1 * 1024 * 1024   # 1MB 제한

def _decode_base64_to_frame(b64str: str):
    """base64 문자열 → OpenCV BGR 이미지(ndarray) 디코드"""
    raw = base64.b64decode(b64str)

    if len(raw) > _MAX_BYTES:
        raise ValueError(
            f"Frame too large ({len(raw)/1024:.1f} KB > {_MAX_BYTES/1024:.1f} KB limit)"
        )

    nparr = np.frombuffer(raw, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Failed to decode image (possibly corrupted base64)")
    return frame


@sio.on("video-frame")
async def handle_video_frame(sid, data):
    """
    클라이언트 → 서버
    data: { "frame": "<base64-encoded-jpeg>" }
    """
    try:
        if not isinstance(data, dict) or "frame" not in data:
            await sio.emit("frame-error", {"error": "missing 'frame' field"}, to=sid)
            return
        frame = _decode_base64_to_frame(data["frame"])
        h, w = frame.shape[:2]
        # await sio.emit(
        #     "frame-ack",
        #     {"status": "ok", "width": w, "height": h},
        #     to=sid
        # )
        # print(f"Received frame from {sid}: {w}x{h}")
    except Exception as e:
        await sio.emit("frame-error", {"error": str(e)}, to=sid)