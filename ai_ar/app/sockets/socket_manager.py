import socketio

# Socket.IO 서버 객체 생성 (ASGI 비동기 모드)
sio = socketio.AsyncServer(
    async_mode='asgi',          # FastAPI 호환
    cors_allowed_origins='*'    # 모든 출처 허용
)

# === 이벤트 정의 ===
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    await sio.emit("server_message", {"msg": "Connected"}, to=sid)

@sio.event
async def disconnect(sid):
    print(f"Disconnected: {sid}", t=sid)

@sio.on("ping")
async def handle_ping(sid, data):
    print(f"📡 Received ping from {sid}: {data}")
    await sio.emit("pong", {"msg": "Pong from FastAPI Server!"}, to=sid)
