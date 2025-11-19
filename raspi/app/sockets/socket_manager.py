# 📄 app/sockets/socket_manager.py

import io
import time
import threading
import socketio
# 주의: sounddevice는 사용하지 않으므로 import 제거 (마이크 리소스 점유 방지)
# import sounddevice as sd
import numpy as np
from datetime import datetime
from threading import Condition
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from libcamera import Transform

# ===== Socket.IO 설정 =====
SERVER_URL = "https://onair.ai.kr"   # EC2 서버 IP
SOCKET_PATH = "/ws"
sio = socketio.Client(reconnection=True, reconnection_attempts=0)  # 무한 재연결

# ===== Picamera2 스트리밍 출력 버퍼 =====
class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.timestamp = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.timestamp = int(time.time() * 1000)
            self.condition.notify_all()
        return len(buf)

# ===== 카메라 제어 클래스 =====
class CameraService:
    def __init__(self):
        self.picam2 = Picamera2()
        self.video_config = self.picam2.create_video_configuration(
            # main={"size": (640, 480), "format": "RGB888"},
            # controls={"FrameRate": 13}
            main={"size": (480, 360), "format": "RGB888"},
            controls={"FrameRate": 10}
        )
        self.picam2.configure(self.video_config)
        self.output = StreamingOutput()
        # self.encoder = JpegEncoder(q=45)
        self.encoder = JpegEncoder(q=35)
        self.file_output = FileOutput(self.output)
        self.is_streaming = False

    def start_streaming(self):
        if not self.is_streaming:
            try:
                print("🎥 Starting Picamera2 streaming...")
                self.picam2.start_recording(self.encoder, self.file_output)
                self.is_streaming = True
            except Exception as e:
                print("⚠️ Camera start error:", e)
                self.is_streaming = False

    def stop_streaming(self):
        if self.is_streaming:
            try:
                print("🛑 Stopping camera stream...")
                self.picam2.stop_recording()
            except Exception as e:
                print("⚠️ Camera stop error:", e)
            self.is_streaming = False

    def get_frame(self):
        with self.output.condition:
            self.output.condition.wait()
            return self.output.frame

# ===== 글로벌 인스턴스 =====
camera = CameraService()
is_streaming = False
stop_signal = threading.Event()

# ===== 비디오 스트리밍 스레드 =====
def stream_loop():
    global is_streaming
    print("🚀 Stream thread started")
    while not stop_signal.is_set():
        if not is_streaming:
            time.sleep(0.1)
            continue

        frame = camera.get_frame()
        if frame:
            try:
                timestamp = int(time.time() * 1000)
                sio.emit(
                    "video_frame",
                    {"timestamp": timestamp, "frame": frame}
                )
            except Exception as e:
                print("⚠️ Emit failed:", e)
                stop_streaming_safe()
                break
        time.sleep(0.05)
    print("🔚 Video Stream thread exiting")

# ===== 안전한 종료 함수 =====
def stop_streaming_safe():
    global is_streaming
    is_streaming = False
    camera.stop_streaming()

# ===== Socket 이벤트 =====
@sio.event
def connect():
    global is_streaming
    print("✅ Connected to EC2 server")
    sio.emit("register_device", {"device": "raspi"})
    
    is_streaming = True
    camera.start_streaming()
    print(" ✅ 비디오 스트리밍 시작 ")

@sio.event
def disconnect():
    print("❌ Disconnected from server")
    stop_streaming_safe()

# ===== 예외 핸들링 =====
@sio.event
def connect_error(data):
    print("⚠️ Connection failed:", data)
    stop_streaming_safe()

@sio.event
def reconnect_error():
    print("⚠️ Reconnection error, will retry...")
    stop_streaming_safe()

# ===== 메인 실행 =====
if __name__ == "__main__":
    print("=" * 60)
    
    threading.Thread(target=stream_loop, daemon=True).start()

    while True:
        try:
            print(f"🔌 Connecting to {SERVER_URL}{SOCKET_PATH} ...")
            sio.connect(SERVER_URL, socketio_path=SOCKET_PATH)
            sio.wait()
        except KeyboardInterrupt:
            print("🛑 Interrupted by user")
            stop_signal.set()
            stop_streaming_safe()
            break
        except Exception as e:
            print("⚠️ Connection failed, retrying in 5s:", e)
            stop_streaming_safe()
            time.sleep(5)
