# 📄 app/sockets/socket_manager.py
# 통합 프로세스: FastAPI Socket.IO 클라이언트, 브리지 클라이언트, WebRTC 오디오/비디오 스트리밍

import io
import time
import threading
import socketio
import sounddevice as sd
import numpy as np
import sys
import os
from datetime import datetime
from threading import Condition
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from libcamera import Transform

# AI_Supporter 경로 추가 (브리지 클라이언트 import용)
# 라즈베리파이 경로: /home/pi/AI_Supporter
# 또는 상대 경로로 설정
ai_supporter_path = os.path.join(os.path.dirname(__file__), '../../..', 'ai_raspi', 'AI_Supporter')
if os.path.exists(ai_supporter_path):
    sys.path.insert(0, ai_supporter_path)
else:
    # 절대 경로 시도
    ai_supporter_path = '/home/pi/AI_Supporter'
    if os.path.exists(ai_supporter_path):
        sys.path.insert(0, ai_supporter_path)

# 브리지 클라이언트 import
try:
    from bridge.stt_bridge_client import SttBridgeClient
    BRIDGE_CLIENT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 브리지 클라이언트를 import할 수 없습니다: {e}")
    print(f"   경로 확인: {ai_supporter_path}")
    BRIDGE_CLIENT_AVAILABLE = False
    SttBridgeClient = None

# ===== Socket.IO 설정 =====
SERVER_URL = "https://onair.ai.kr"   # EC2 서버 IP
SOCKET_PATH = "/ws"
sio = socketio.Client(reconnection=True, reconnection_attempts=0)  # 무한 재연결

# ===== 브리지 클라이언트 인스턴스 =====
bridge_client = None

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
            if not self.is_streaming:
                return

            length = len(indata)
            if self.buffer_index + length >= len(self.buffer):
                # 버퍼가 꽉 찼을 때 한 덩어리 전송
                self.buffer[self.buffer_index:self.buffer_index+length] = indata[:, 0]

                try:
                    timestamp = int(time.time() * 1000)  # 현재 시각 (ms 단위)
                    sio.emit(
                        "audio_frame",
                        {
                            "timestamp": timestamp,
                            "frame": self.buffer.tobytes(),
                        }
                    )
                except Exception as e:
                    print("⚠️ Audio emit error:", e)

                self.buffer_index = 0
            else:
                # 버퍼 아직 덜 찼을 때
                self.buffer[self.buffer_index:self.buffer_index+length] = indata[:, 0]
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

# ===== STT 결과 전송 함수 (동기 버전, 스레드 안전) =====
# FastAPI Socket.IO 클라이언트 접근을 위한 락
_sio_lock = threading.Lock()

def emit_stt_result(stt_data: dict):
    """
    STT 결과를 FastAPI 서버로 전송 (동기 버전, 스레드 안전)
    
    Args:
        stt_data: STT 결과 딕셔너리
            예: {"type": "final", "text": "안녕하세요", "confidence": 0.95}
            Streaming STT의 경우: {"type": "final", "text": "...", "session_id": "uuid", ...}
    """
    with _sio_lock:
        if not sio.connected:
            print("⚠️ Socket.IO 서버에 연결되어 있지 않습니다. STT 결과 전송 불가")
            return False
        
        try:
            sio.emit("stt_result", stt_data)
            print(f"📤 STT 결과 전송: {stt_data.get('type', 'unknown')} - {stt_data.get('text', '')[:50]}...")
            return True
        except Exception as e:
            print(f"❌ STT 결과 전송 오류: {e}")
            return False

def emit_wakeword_detected():
    """
    Wakeword 감지 이벤트를 FastAPI 서버로 전송 (동기 버전, 스레드 안전)
    """
    with _sio_lock:
        if not sio.connected:
            print("⚠️ Socket.IO 서버에 연결되어 있지 않습니다. Wakeword 감지 이벤트 전송 불가")
            return False
        
        try:
            sio.emit("wakeword_detected", {})
            print("📤 Wakeword 감지 이벤트 전송 완료")
            return True
        except Exception as e:
            print(f"❌ Wakeword 감지 이벤트 전송 오류: {e}")
            return False

# ===== 동기 Socket.IO 클라이언트 래퍼 (브리지 클라이언트용) =====
class SyncSocketIOClient:
    """
    동기 Socket.IO 클라이언트 래퍼
    브리지 클라이언트가 동기 클라이언트를 받을 수 있도록 래퍼 제공
    내부 함수에서 락을 사용하므로 여기서는 락을 사용하지 않음 (데드락 방지)
    """
    def __init__(self, sio_client):
        self.sio = sio_client
    
    def is_connected(self):
        """연결 상태 확인 (스레드 안전)"""
        # 내부 함수에서 락을 사용하므로 여기서는 직접 접근
        return self.sio.connected if hasattr(self.sio, 'connected') else False
    
    def emit_stt_result(self, stt_data: dict):
        """STT 결과 전송 (동기 버전, 스레드 안전)"""
        # 내부 함수에서 락을 사용하므로 여기서는 직접 호출
        return emit_stt_result(stt_data)
    
    def emit_wakeword_detected(self):
        """Wakeword 감지 이벤트 전송 (동기 버전, 스레드 안전)"""
        # 내부 함수에서 락을 사용하므로 여기서는 직접 호출
        return emit_wakeword_detected()

# ===== Socket 이벤트 =====
@sio.event
def connect():
    global is_streaming, bridge_client
    print("✅ Connected to EC2 server")
    sio.emit("register_device", {"device": "raspi"})

    # 연결 시 비디오만 자동 스트리밍 시작 (오디오는 서버 이벤트로 시작)
    is_streaming = True
    camera.start_streaming()
    
    # 브리지 클라이언트 초기화 및 연결 (첫 연결 시)
    if BRIDGE_CLIENT_AVAILABLE and bridge_client is None:
        try:
            print("=" * 60)
            print("🔌 브리지 클라이언트 초기화 중...")
            print("=" * 60)
            bridge_client = SttBridgeClient()
            # 동기 클라이언트 래퍼 주입
            sync_client = SyncSocketIOClient(sio)
            bridge_client.set_fastapi_socketio_client(sync_client)
            print("✅ FastAPI Socket.IO 클라이언트 주입 완료")
            
            # 브리지 서버 연결을 별도 스레드에서 실행 (블로킹 방지)
            def bridge_connect_thread():
                """브리지 클라이언트 연결을 별도 스레드에서 실행"""
                try:
                    print("=" * 60)
                    print("🔄 브리지 클라이언트 연결 스레드 시작")
                    print("=" * 60)
                    bridge_client.connect()
                except Exception as e:
                    print("=" * 60)
                    print(f"❌ 브리지 클라이언트 연결 스레드 오류: {e}")
                    print("=" * 60)
                    import traceback
                    traceback.print_exc()
            
            bridge_thread = threading.Thread(target=bridge_connect_thread, daemon=True)
            bridge_thread.start()
            print("✅ 브리지 클라이언트 초기화 완료 (연결 시도 중)")
            print("   💡 브리지 서버 연결 완료까지 최대 10초 소요될 수 있습니다.")
            print("   💡 Python 3.10 프로세스(main_py310.py)가 실행 중이어야 합니다.")
            print("   💡 브리지 클라이언트는 별도 스레드에서 실행됩니다 (블로킹 방지).")
            print("=" * 60)
        except Exception as e:
            print("=" * 60)
            print(f"⚠️ 브리지 클라이언트 초기화 실패: {e}")
            print("=" * 60)
            import traceback
            traceback.print_exc()

@sio.event
def handle_audio_stream(data):
    """서버에서 오디오 스트리밍 시작 이벤트 수신"""
    if data.get("start", False):
        print("🎙️ Audio streaming start signal received from server")
        audio.start_streaming()
    else:
        print("🛑 Audio streaming stop signal received from server")
        audio.stop_streaming()

# ===== FastAPI 서버로부터 이벤트 수신 (STT 관련) =====
@sio.on("stop_streaming_stt")
def handle_stop_streaming_stt(data):
    """Streaming STT 종료 신호 수신"""
    session_id = data.get("session_id")
    reason = data.get("reason", "unknown")
    print("=" * 60)
    print(f"🛑 Streaming STT 종료 신호 수신: session_id={session_id}, reason={reason}")
    print("=" * 60)
    
    # 브리지 서버를 통해 Python 3.10으로 전달
    if bridge_client and bridge_client.is_connected():
        try:
            bridge_client.sio.emit('stop_streaming_stt', {
                "session_id": session_id,
                "reason": reason
            })
            print("✅ 브리지 서버로 Streaming STT 종료 신호 전송 완료")
        except Exception as e:
            print(f"❌ 브리지 서버로 Streaming STT 종료 신호 전송 실패: {e}")
    else:
        print("⚠️ 브리지 서버에 연결되어 있지 않습니다.")

@sio.on("start_streaming_stt")
def handle_start_streaming_stt(data):
    """Streaming STT 시작 신호 수신 (FastAPI 서버에서 전송)"""
    session_id = data.get("session_id")
    message = data.get("message", "")
    print("=" * 60)
    print(f"📩 start_streaming_stt 이벤트 수신")
    print(f"   Session ID: {session_id}")
    print(f"   Message: {message}")
    print("=" * 60)
    
    # 브리지 서버를 통해 Python 3.10으로 Streaming STT 시작 명령 전송
    if bridge_client and bridge_client.is_connected():
        success = bridge_client.emit_start_streaming_stt(session_id)
        if success:
            print("✅ 브리지 서버로 Streaming STT 시작 명령 전송 완료")
        else:
            print("❌ 브리지 서버로 Streaming STT 시작 명령 전송 실패")
    else:
        print("⚠️ 브리지 서버에 연결되어 있지 않습니다.")

@sio.on("cv_detection_failed")
def handle_cv_detection_failed(data):
    """CV 모델 오류 탐지 실패 이벤트 수신 (AI_SUPPORTER 분기)"""
    message = data.get("message", "")
    print("=" * 60)
    print(f"📩 cv_detection_failed 이벤트 수신")
    print(f"   메시지: {message}")
    print("=" * 60)
    print("⏳ 모바일 CV 탐지 실패 음성 파일 재생 완료 이벤트 대기 중...")
    print("   start_streaming_stt 이벤트 수신 후 Streaming STT 세션을 시작합니다.")
    print("=" * 60)

@sio.on("wakeword_start_waiting")
def handle_wakeword_start_waiting(data):
    """Wakeword 감지 대기 시작 이벤트 수신"""
    print("=" * 60)
    print(f"📩 Wakeword 감지 대기 시작 이벤트 수신")
    print("=" * 60)
    
    # 브리지 서버를 통해 Python 3.10으로 Wakeword 감지 대기 시작 신호 전달
    if bridge_client and bridge_client.is_connected():
        try:
            bridge_client.sio.emit('wakeword_start_waiting', {})
            print("✅ 브리지 서버로 Wakeword 감지 대기 시작 신호 전송 완료")
        except Exception as e:
            print(f"❌ 브리지 서버로 Wakeword 감지 대기 시작 신호 전송 실패: {e}")
    else:
        print("⚠️ 브리지 서버에 연결되어 있지 않습니다.")

@sio.on("mic_off")
def handle_mic_off(data):
    """STT 목적 음성 수집 중지 이벤트 수신"""
    print("=" * 60)
    print(f"📩 STT 목적 음성 수집 중지 이벤트 수신")
    print("   주의: 마이크는 하나이며, STT 목적으로 사용 중이던 스트림을 중지합니다.")
    print("=" * 60)
    
    # 브리지 서버를 통해 Python 3.10으로 마이크 OFF 신호 전달
    if bridge_client and bridge_client.is_connected():
        try:
            bridge_client.sio.emit('mic_off', {})
            print("✅ 브리지 서버로 마이크 OFF 신호 전송 완료")
        except Exception as e:
            print(f"❌ 브리지 서버로 마이크 OFF 신호 전송 실패: {e}")
    else:
        print("⚠️ 브리지 서버에 연결되어 있지 않습니다.")

@sio.on("mic_on")
def handle_mic_on(data):
    """STT 목적 음성 수집 재개 이벤트 수신"""
    print("=" * 60)
    print(f"📩 STT 목적 음성 수집 재개 이벤트 수신")
    print("   주의: 마이크는 하나이며, STT 목적으로 음성을 수집합니다.")
    print("=" * 60)
    
    # 브리지 서버를 통해 Python 3.10으로 마이크 ON 신호 전달
    if bridge_client and bridge_client.is_connected():
        try:
            bridge_client.sio.emit('mic_on', {})
            print("✅ 브리지 서버로 마이크 ON 신호 전송 완료")
        except Exception as e:
            print(f"❌ 브리지 서버로 마이크 ON 신호 전송 실패: {e}")
    else:
        print("⚠️ 브리지 서버에 연결되어 있지 않습니다.")

@sio.on("service_completed")
def handle_service_completed(data):
    """서비스 완료 이벤트 수신 (GPT-4o 답변 생성 및 TTS 완료 후)"""
    session_id = data.get("session_id", "")
    status = data.get("status", "")
    print("=" * 60)
    print(f"✅ service_completed 이벤트 수신 (FastAPI 서버)")
    print(f"   Session ID: {session_id}, Status: {status}")
    print("=" * 60)
    
    # 브리지 서버를 통해 Python 3.10으로 서비스 완료 신호 전달
    if bridge_client and bridge_client.is_connected():
        try:
            bridge_client.sio.emit('service_completed', {
                "session_id": session_id,
                "status": status
            })
            print("✅ 브리지 서버로 서비스 완료 신호 전송 완료")
        except Exception as e:
            print(f"❌ 브리지 서버로 서비스 완료 신호 전송 실패: {e}")
    else:
        print("⚠️ 브리지 서버에 연결되어 있지 않습니다.")

@sio.on("wakeword_audio_completed")
def handle_wakeword_audio_completed(data):
    """모바일 음성 파일 재생 완료 이벤트 수신 (FastAPI 서버에서 전송)"""
    print("=" * 60)
    print(f"📥 wakeword_audio_completed 이벤트 수신 (FastAPI 서버)")
    print("=" * 60)
    
    # 브리지 서버를 통해 Python 3.10으로 모바일 음성 파일 재생 완료 신호 전달
    if bridge_client and bridge_client.is_connected():
        try:
            bridge_client.sio.emit('wakeword_audio_completed', {})
            print("✅ 브리지 서버로 모바일 음성 파일 재생 완료 신호 전송 완료")
        except Exception as e:
            print(f"❌ 브리지 서버로 모바일 음성 파일 재생 완료 신호 전송 실패: {e}")
    else:
        print("⚠️ 브리지 서버에 연결되어 있지 않습니다.")

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

# ===== 브리지 클라이언트 연결 상태 확인 함수 =====
def check_bridge_client_status():
    """브리지 클라이언트 연결 상태를 확인하고 출력"""
    if not BRIDGE_CLIENT_AVAILABLE:
        print("⚠️ 브리지 클라이언트를 사용할 수 없습니다 (import 실패)")
        return False
    
    if bridge_client is None:
        print("⚠️ 브리지 클라이언트가 초기화되지 않았습니다")
        return False
    
    if bridge_client.is_connected():
        print("✅ 브리지 클라이언트 연결 상태: 연결됨")
        return True
    else:
        print("⚠️ 브리지 클라이언트 연결 상태: 연결 안 됨 (Python 3.10 프로세스 확인 필요)")
        return False

# ===== 메인 실행 =====
if __name__ == "__main__":
    threading.Thread(target=stream_loop, daemon=True).start()
    
    # 브리지 클라이언트 상태 확인 스레드 (주기적으로 상태 출력)
    def status_checker():
        """주기적으로 브리지 클라이언트 상태 확인"""
        while True:
            time.sleep(10)  # 10초마다 확인
            if bridge_client is not None:
                check_bridge_client_status()
    
    threading.Thread(target=status_checker, daemon=True).start()

    while True:
        try:
            print(f"🔌 Connecting to {SERVER_URL}{SOCKET_PATH} ...")
            sio.connect(SERVER_URL, socketio_path=SOCKET_PATH)
            
            # 연결 후 브리지 클라이언트 상태 확인
            time.sleep(2)  # 연결 후 잠시 대기
            if bridge_client is not None:
                print("=" * 60)
                print("📊 브리지 클라이언트 연결 상태 확인")
                print("=" * 60)
                check_bridge_client_status()
                print("=" * 60)
            
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
