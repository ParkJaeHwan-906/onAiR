import socketio
import asyncio
from app.services.camera_service import start_stream, stop_stream

# ASGI 모드용 Socket.IO 서버 생성
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*'
)

# 이벤트 등록
@sio.event
async def connect(sid, environ):
    print(f"✅ Socket connected: {sid}")
    await sio.emit("message", {"msg": "Connected to Raspberry Pi"}, to=sid)

@sio.event
async def disconnect(sid):
    print(f"❌ Socket disconnected: {sid}")

@sio.on("video_stream")
async def handle_video_stream(sid, data):
    """
    클라이언트에서 {"state": "on"} or {"state": "off"} 형태로 요청
    """
    state = data.get("state", "off")
    print(f"🎥 Received video_stream event: {state}")

    if state == "on":
        # ✅ start_stream() 호출 (callback에서 프레임 emit)
        def emit_frame(b64_frame, sid=None):
            if sid:
                asyncio.create_task(
                    sio.emit("video-frame", {"frame": b64_frame}, to=sid)
                )
            else:
                asyncio.create_task(
                    sio.emit("video-frame", {"frame": b64_frame})
                )
        start_stream(emit_frame)
        await sio.emit("stream_status", {"result": "started"}, to=sid)

    elif state == "off":
        # ✅ stop_stream() 호출
        stop_stream()
        await sio.emit("stream_status", {"result": "stopped"}, to=sid)

    else:
        await sio.emit("stream_status", {"result": "unknown state"}, to=sid)