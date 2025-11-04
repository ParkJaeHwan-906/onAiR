from app.sockets.socket_manager import sio
from app.ar import motion_core, anchor_manager
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


# 🎥 프레임 처리 이벤트
@sio.on("video-frame")
async def handle_video_frame(sid, data):
    """클라이언트 → 서버: data: { "frame": "<base64-encoded-jpeg>" }"""
    try:
        if not isinstance(data, dict) or "frame" not in data:
            await sio.emit("frame-error", {"error": "missing 'frame' field"}, to=sid)
            return

        # ✅ 1. base64 → frame
        frame = _decode_base64_to_frame(data["frame"])

        # ✅ 2. motion_core 계산 수행
        result = motion_core.process_frame(frame)

        # ✅ 3. 필요하다면 원본 프레임을 그대로 보내기
        # (frame을 직접 보낼 수 없으므로 base64로 다시 인코딩)
        _, buf = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buf).decode('utf-8')

        await sio.emit("frame-video", {"frame": frame_b64}, to=sid)
        await sio.emit("motion-update", result, to=sid)

    except Exception as e:
        await sio.emit("frame-error", {"error": str(e)}, to=sid)


# 📍 앵커 추가 (클릭 좌표)
@sio.on("add-anchor")
async def handle_add_anchor(sid, data):
    """
    클라이언트 → 서버
    data: { "x": <int>, "y": <int> }
    """
    try:
        x, y = data.get("x"), data.get("y")
        if x is None or y is None:
            await sio.emit("anchor-error", {"error": "x/y not provided"}, skip_sid=sid)

        anchor = anchor_manager.add_anchor(
            x, y,
            motion_core.last_inlier_old,
            motion_core.last_inlier_new,
            motion_core.K_global,
            motion_core.R_total,
            motion_core.t_total
        )

        await sio.emit("anchor-added", anchor, skip_sid=sid)

    except Exception as e:
        await sio.emit("anchor-error", {"error": str(e)}, skip_sid=sid)