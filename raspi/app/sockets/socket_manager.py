# 📄 app/sockets/socket_manager.py
import socketio
from app.services.camera_service import start_stream, stop_stream

# Socket.IO 클라이언트 객체 생성
sio = socketio.Client()

# 서버 연결 이벤트
@sio.event
def connect():
    print("✅ Connected to EC2 Socket Server")

@sio.event
def disconnect():
    print("❌ Disconnected from EC2 Socket Server")

@sio.on("message")
def on_message(data):
    print("📩 Message from server:", data)
