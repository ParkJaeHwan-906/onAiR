# 📄 app/sockets/socket_manager.py
import socketio
import cv2
import base64
import threading
from app.services.camera_service import start_stream, stop_stream

# Socket.IO 클라이언트 객체 생성
sio = socketio.Client()
cap = None
is_streaming = False

# 카메라 스레드 함수
def stream_camera():
    global cap, is_streaming

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1080)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 15)

    print("🎥 Camera streaming started")

    while is_streaming and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # JPEG 인코딩
        _, buffer = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buffer).decode('utf-8')

        # Socket 이벤트 전송
        sio.emit("frame-video", {"frame": frame_b64})

        # 15fps 정도 유지
        cv2.waitKey(int(1000 / 15))

    cap.release()
    print("🛑 Camera streaming stopped")

# 서버 연결 이벤트
@sio.event
def connect():
    print("✅ Connected to server")
    # 연결 후 디바이스 타입 등록
    sio.emit("register_device", {"device": "raspi"})
    
@sio.event
def disconnect():
    print("❌ Disconnected from EC2 Socket Server")

@sio.on("video_stream")
def on_video_stream(data):
    global is_streaming

    state = data.get("state", "off")
    print(f"📡 Received video_stream: {state}")

    if state == "on" and not is_streaming:
        is_streaming = True
        threading.Thread(target=stream_camera, daemon=True).start()
    elif state == "off" and is_streaming:
        is_streaming = False