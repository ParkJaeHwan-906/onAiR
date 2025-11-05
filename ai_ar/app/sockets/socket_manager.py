# 📄 app/sockets/socket_manager.py
import socketio
import os
import cv2
import numpy as np
from datetime import datetime

# 비동기 Socket.IO 서버 생성
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*'
)

# 클라이언트별 디바이스 타입 저장용
device_map = {}   # { sid: "raspi" / "mobile" / "pc" }

# === 이벤트 정의 ===
@sio.event
async def connect(sid, environ):
    print(f"✅ Client connected: {sid}")
    await sio.emit("server_message", {"msg": "Connected"}, to=sid)


@sio.event
async def disconnect(sid):
    print(f"❌ Disconnected: {sid}")
    # 연결 종료 시 기록 삭제
    if sid in device_map:
        print(f"🧹 Removing device: {device_map[sid]}")
        del device_map[sid]


@sio.on("register_device")
async def register_device(sid, data):
    """
    클라이언트에서 {'device': 'raspi'} 형태로 등록 요청
    """
    device = data.get("device", "unknown")
    device_map[sid] = device
    await sio.save_session(sid, {"device": device})

    print(f"🔗 Registered device: {device} ({sid})")
    await sio.emit("server_message", {"msg": f"Device '{device}' registered"}, to=sid)


@sio.on("ping")
async def handle_ping(sid, data):
    session = await sio.get_session(sid)
    device = session.get("device", "unknown")
    print(f"📡 Received ping from [{device}] {sid}: {data}")
    await sio.emit("pong", {"msg": f"Pong from server to {device}!"}, to=sid)


# === 타입별 브로드캐스트 ===
async def broadcast_to(device_types, event: str, payload: dict):
    """
    특정 디바이스 타입(하나 또는 여러 개)에 이벤트 전송
    - device_types: 문자열('raspi') 또는 리스트(['raspi', 'mobile'])
    """
    if isinstance(device_types, str):
        device_types = [device_types]

    sent_count = 0
    for sid, dev in device_map.items():
        if dev in device_types:
            await sio.emit(event, payload, to=sid)
            sent_count += 1

    print(f"📡 Broadcasted '{event}' to {sent_count} clients ({device_types})")


# === video_stream ===
@sio.on("video_stream")
async def handle_video_stream(sid, data):
    """
    PC/Mobile → Raspi로 영상 스트리밍 제어 신호 전달
    """
    sender_device = device_map.get(sid, "unknown")
    state = data.get("state", "off")

    print(f"📡 Received 'video_stream:{state}' from {sender_device}")
    await broadcast_to("raspi", "video_stream", {"state": state})


# === video-frame (라즈베리 → 서버 프레임 전송) ===
@sio.on("video-frame")
async def handle_video_frame(sid, data):
    """
    라즈베리파이에서 binary 형태로 전송된 JPEG 프레임 처리
    """
    sender_device = device_map.get(sid, "unknown")

    if not data:
        return

    # data는 bytes (JPEG 이미지)
    np_data = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)

    if frame is None:
        print("⚠️ Failed to decode frame")
        return

    print(f"🎞️ Received frame from {sender_device}")

    # 동시에 PC 클라이언트에게 브로드캐스트
    _, jpeg_bytes = cv2.imencode('.jpg', frame)
    await broadcast_to("pc", "video_frame", jpeg_bytes.tobytes())
