# 📄 app/sockets/socket_manager.py

import io
import time
import threading
import socketio
import sounddevice as sd
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
            main={"size": (640, 480), "format": "RGB888"},
            controls={"FrameRate": 13}
        )
        self.picam2.configure(self.video_config)
        self.output = StreamingOutput()
        self.encoder = JpegEncoder(q=45)
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

# ===== 오디오 제어 클래스 =====
class AudioService:
    def __init__(self, rate=16000, chunk=1024, send_chunk=4):
        self.rate = rate
        self.chunk = chunk
        self.send_chunk = send_chunk
        self.is_streaming = False
        self.stream = None  # 스트림 객체 저장용
        self.buffer = np.zeros((chunk*send_chunk,), dtype=np.float32)
        self.buffer_index = 0
    
    def start_streaming(self):
        if not self.is_streaming:
            print("🎙️ Starting microphone stream...")
            self.is_streaming = True
            threading.Thread(target=self.stream_audio, daemon=True).start()
    
    def stop_streaming(self):
        """오디오 스트리밍 종료"""
        if self.is_streaming:
            print("🛑 Stopping microphone stream...")
            self.is_streaming = False
            # 스트림이 열려있으면 명시적으로 닫기
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as e:
                    print(f"⚠️ Stream close error: {e}")
                finally:
                    self.stream = None

    def stream_audio(self):
        def callback(indata, frames, time_info, status):
            if not self.is_streaming: return

            length = len(indata)
            if self.buffer_index + length >= len(self.buffer):
                # 버퍼 채워짐 → 서버로 전송
                self.buffer[self.buffer_index:self.buffer_index+length] = indata[:,0]
                try:
                    sio.emit("audio_frame", self.buffer.tobytes())
                except Exception as e:
                    print("⚠️ Audio emit error:", e)
                self.buffer_index = 0
            else:
                # 아직 버퍼 채우기
                self.buffer[self.buffer_index:self.buffer_index+length] = indata[:,0]
                self.buffer_index += length

        try:
            self.stream = sd.InputStream(
                channels=1,
                samplerate=self.rate,
                blocksize=self.chunk,
                callback=callback
            )
            self.stream.start()
            # 스트리밍이 활성화된 동안 대기
            while self.is_streaming:
                time.sleep(0.05)
        except Exception as e:
            print(f"⚠️ Audio stream error: {e}")
        finally:
            # 스트림 정리
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except:
                    pass
                self.stream = None
            print("🔇 Microphone stream closed")

# ===== 글로벌 인스턴스 =====
camera = CameraService()
audio = AudioService()
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
    audio.stop_streaming()

# ===== Socket 이벤트 =====
@sio.event
def connect():
    global is_streaming
    print("✅ Connected to EC2 server")
    sio.emit("register_device", {"device": "raspi"})

    # 연결 시 비디오만 자동 스트리밍 시작 (오디오는 서버 이벤트로 시작)
    is_streaming = True
    camera.start_streaming()

@sio.event
def handle_audio_stream(data):
    """서버에서 오디오 스트리밍 시작 이벤트 수신"""
    if data.get("start", False):
        print("🎙️ Audio streaming start signal received from server")
        audio.start_streaming()
    else:
        print("🛑 Audio streaming stop signal received from server")
        audio.stop_streaming()

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
