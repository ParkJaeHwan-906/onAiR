import socketio

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

@sio.on("led_control")
async def handle_led_control(sid, data):
    print("DSadas")
    """
    클라이언트에서 {"state": "on"} or {"state": "off"} 형태로 요청
    """
    await sio.emit("led_status", {"result": 1}, to=sid)
