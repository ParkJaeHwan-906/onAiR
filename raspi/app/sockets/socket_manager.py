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
# class AudioService:
#     def __init__(self, rate=16000, chunk=1024, send_chunk=4):
#         self.rate = rate
#         self.chunk = chunk
#         self.send_chunk = send_chunk
#         self.is_streaming = False
#         self.stream = None  # 스트림 객체 저장용
#         self.buffer = np.zeros((chunk*send_chunk,), dtype=np.float32)
#         self.buffer_index = 0
    
#     def start_streaming(self):
#         if not self.is_streaming:
#             print("🎙️ Starting microphone stream for WebRTC...")
#             print("   ⚠️ Python 3.10 프로세스(main_py310.py)의 마이크 사용이 중지됩니다.")
#             self.is_streaming = True
#             threading.Thread(target=self.stream_audio, daemon=True).start()
    
#     def stop_streaming(self):
#         """오디오 스트리밍 종료"""
#         if self.is_streaming:
#             print("🛑 Stopping microphone stream for WebRTC...")
#             print("   ✅ 마이크가 해제되었습니다. Python 3.10 프로세스가 마이크를 사용할 수 있습니다.")
#             self.is_streaming = False
#             # 스트림이 열려있으면 명시적으로 닫기
#             if self.stream is not None:
#                 try:
#                     self.stream.stop()
#                     self.stream.close()
#                 except Exception as e:
#                     print(f"⚠️ Stream close error: {e}")
#                 finally:
#                     self.stream = None

#     def stream_audio(self):
#         # 스트림 시작 시 버퍼 인덱스 초기화
#         self.buffer_index = 0
        
#         def callback(indata, frames, time_info, status):
#             if not self.is_streaming: return

#             length = len(indata)
#             if self.buffer_index + length >= len(self.buffer):
#                 # 버퍼 채워짐 → 서버로 전송
#                 self.buffer[self.buffer_index:self.buffer_index+length] = indata[:,0]
#                 try:
#                     sio.emit("audio_frame", self.buffer.tobytes())
#                 except Exception as e:
#                     print("⚠️ Audio emit error:", e)
#                 self.buffer_index = 0
#             else:
#                 # 아직 버퍼 채우기
#                 self.buffer[self.buffer_index:self.buffer_index+length] = indata[:,0]
#                 self.buffer_index += length

#         # 마이크 장치를 명시적으로 지정하지 않음 (기본 장치 사용)
#         # STT 프로세스가 마이크를 해제한 후 WebRTC가 시작되므로 충돌 방지
#         # 주의: is_streaming이 False가 되면 즉시 종료
#         max_retries = 3
#         retry_delay = 0.5
        
#         for attempt in range(max_retries):
#             # is_streaming이 False가 되면 즉시 종료
#             if not self.is_streaming:
#                 print("🔇 오디오 스트리밍 중지 신호 수신, 스트림 시작 취소")
#                 break
                
#             try:
#                 print(f"🎙️ WebRTC 오디오 스트림 시작 시도 {attempt + 1}/{max_retries}...")
#                 self.stream = sd.InputStream(
#                     channels=1,
#                     samplerate=self.rate,
#                     blocksize=self.chunk,
#                     callback=callback,
#                     device=None  # 기본 장치 사용 (STT 프로세스가 해제한 후 사용)
#                 )
#                 self.stream.start()
#                 print("✅ WebRTC 오디오 스트림 시작 성공")
#                 print("   ⚠️ 마이크가 WebRTC 프로세스에 의해 점유되었습니다.")
#                 # 스트리밍이 활성화된 동안 대기
#                 while self.is_streaming:
#                     time.sleep(0.05)
#                 print("🔇 WebRTC 오디오 스트림 종료 (is_streaming=False)")
#                 break
#             except Exception as e:
#                 print(f"⚠️ Audio stream error (시도 {attempt + 1}/{max_retries}): {e}")
#                 if attempt < max_retries - 1:
#                     print(f"   {retry_delay}초 후 재시도...")
#                     time.sleep(retry_delay)
#                     retry_delay *= 2  # 지수 백오프
#                 else:
#                     print("❌ WebRTC 오디오 스트림 시작 실패 (최대 재시도 횟수 초과)")
#             finally:
#                 # 스트림 정리
#                 if self.stream is not None:
#                     try:
#                         self.stream.stop()
#                         self.stream.close()
#                         print("🔇 WebRTC 마이크 스트림 닫기 완료")
#                     except Exception as e:
#                         print(f"⚠️ 스트림 닫기 오류 (무시 가능): {e}")
#                     finally:
#                         self.stream = None
#                 if attempt == max_retries - 1 or self.is_streaming == False:
#                     print("🔇 Microphone stream closed")

# ===== 글로벌 인스턴스 =====
camera = CameraService()
# audio = AudioService()
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
    # audio.stop_streaming()

# ===== Socket 이벤트 =====
@sio.event
def connect():
    global is_streaming
    print("✅ Connected to EC2 server")
    sio.emit("register_device", {"device": "raspi"})

    # 연결 시 비디오만 자동 스트리밍 시작 (오디오는 서버 이벤트로 시작)
    # 주의: 오디오 스트리밍은 handle_audio_stream 이벤트를 받을 때만 시작
    # 평소에는 마이크를 점유하지 않음 (Python 3.10 프로세스가 우선)
    
    # 연결 시 오디오 스트리밍이 실행 중이면 명시적으로 중지 (재연결 시 안전장치)
    # if audio.is_streaming:
    #     print("⚠️ 연결 시 오디오 스트리밍이 실행 중이었습니다. 중지합니다.")
    #     audio.stop_streaming()
    
    is_streaming = True
    camera.start_streaming()
    # 오디오는 시작하지 않음 - handle_audio_stream 이벤트를 받을 때만 시작
    print("   ✅ 비디오 스트리밍 시작 (오디오는 handle_audio_stream 이벤트를 받을 때만 시작)")

# @sio.event
# def handle_audio_stream(data):
#     """서버에서 오디오 스트리밍 시작/중지 이벤트 수신"""
#     if data.get("start", False):
#         print("🎙️ Audio streaming start signal received from server")
#         print("   ⚠️ WebRTC 오디오 스트리밍 시작: Python 3.10 프로세스의 마이크 사용이 중지됩니다.")
#         audio.start_streaming()
#     else:
#         print("🛑 Audio streaming stop signal received from server")
#         print("   ✅ WebRTC 오디오 스트리밍 중지: Python 3.10 프로세스가 마이크를 사용할 수 있습니다.")
#         audio.stop_streaming()

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
    # 프로세스 시작 시 오디오 스트리밍이 중지 상태인지 확인
    print("=" * 60)
    print("🔍 초기 상태 확인: 오디오 스트리밍 중지 상태 확인")
    print("=" * 60)
    # if audio.is_streaming:
    #     print("⚠️ 프로세스 시작 시 오디오 스트리밍이 실행 중이었습니다. 중지합니다.")
    #     audio.stop_streaming()
    # if audio.stream is not None:
    #     print("⚠️ 프로세스 시작 시 마이크 스트림이 열려있었습니다. 닫습니다.")
    #     try:
    #         audio.stream.stop()
    #         audio.stream.close()
    #     except:
    #         pass
    #     audio.stream = None
    print("   ✅ 오디오 스트리밍은 중지 상태입니다. (handle_audio_stream 이벤트를 받을 때만 시작)")
    print("   ✅ 마이크 스트림은 닫혀있습니다.")
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
