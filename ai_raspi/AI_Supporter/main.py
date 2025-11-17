"""
라즈베리파이 메인 프로그램 (Python 3.13용)
- Socket.IO 클라이언트 실행 (Python 3.13에서만 동작)
- 브리지 서버 실행 (Python 3.10에서 오는 STT 결과 수신)
- 브리지 클라이언트 실행 (STT 결과를 Socket.IO로 전송)
"""
import threading
import asyncio
import logging
import json
from stt.socketio_client import SocketIOClient
from bridge.stt_bridge_client import SttBridgeClient
from server.app import manager  # manager만 사용 (app은 레거시)
from config import settings

# Streaming STT는 Python 3.10에서만 동작하므로, 
# Python 3.13에서는 인스턴스를 생성하지 않고 None으로 설정
# 실제 Streaming STT는 Python 3.10 프로세스에서 처리됨
try:
    from stt.gcp_stt_stream import GcpStreamingStt
    from stt.mic_stream import MicStream
    STREAMING_STT_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ Streaming STT를 사용할 수 없습니다 (Python 3.10에서만 동작): {e}")
    STREAMING_STT_AVAILABLE = False

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_socketio_client():
    """
    Socket.IO 클라이언트 및 브리지 클라이언트 실행 (Python 3.13에서 실행)
    - Socket.IO 클라이언트: FastAPI 서버와 통신
    - 브리지 서버: Python 3.10에서 오는 STT 결과 수신
    - 브리지 클라이언트: STT 결과를 Socket.IO로 전송
    """
    # 이벤트 루프 생성
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Socket.IO 클라이언트 초기화
    socketio_client = SocketIOClient(manager=manager)
    manager.set_socketio_client(socketio_client)
    
    # Streaming STT 인스턴스 생성 및 등록 (Python 3.13에서 사용 가능한 경우)
    # 주의: 실제 Streaming STT는 Python 3.10에서 실행되지만,
    # cv_detection_failed 이벤트 처리를 위해 인스턴스가 필요함
    if STREAMING_STT_AVAILABLE:
        try:
            # MicStream은 Python 3.10에서만 사용 가능하므로 None으로 설정
            # 실제 마이크 스트림은 Python 3.10 프로세스에서 관리됨
            streaming_stt = GcpStreamingStt(socketio_client=socketio_client)
            manager.set_streaming_stt_instance(streaming_stt)
            logger.info("✅ Streaming STT 인스턴스 등록 완료")
        except Exception as e:
            logger.warning(f"⚠️ Streaming STT 인스턴스 생성 실패: {e}")
            logger.warning("   Streaming STT는 Python 3.10 프로세스에서 처리됩니다.")
    else:
        logger.info("ℹ️ Streaming STT는 Python 3.10 프로세스에서 처리됩니다.")
    
    # 브리지 클라이언트 초기화
    bridge_client = SttBridgeClient()
    bridge_client.set_fastapi_socketio_client(socketio_client)  # FastAPI 클라이언트 주입
    manager.bridge_client = bridge_client  # manager에 브리지 클라이언트 등록
    logger.info("✅ 브리지 클라이언트 초기화 완료")
    
    # WebRTC 오디오 스트리머 초기화 (Python 3.13에서 실행)
    try:
        from audio.audio_streamer import AudioStreamer
        audio_streamer = AudioStreamer(socketio_client=socketio_client)
        manager.set_audio_streamer(audio_streamer)
        logger.info("✅ 오디오 스트리머 초기화 완료")
    except ImportError as e:
        logger.warning(f"⚠️ 오디오 스트리머를 사용할 수 없습니다: {e}")
        logger.warning("   sounddevice 라이브러리가 필요합니다.")
    except Exception as e:
        logger.warning(f"⚠️ 오디오 스트리머 초기화 실패: {e}")
    
    async def main_async():
        """비동기 메인 함수"""
        # Socket.IO 서버 연결
        try:
            connected = await socketio_client.connect()
            if connected:
                logger.info(f"✅ Socket.IO 서버 연결 성공: {settings.FASTAPI_SERVER_URL} (경로: /ws)")
            else:
                logger.warning(f"⚠️ Socket.IO 서버 연결 실패: {settings.FASTAPI_SERVER_URL}")
                return
        except Exception as e:
            logger.error(f"❌ Socket.IO 연결 오류: {e}")
            return
        

        
        # 브리지 클라이언트 연결 (별도 스레드에서 실행)
        # 주의: 브리지 서버는 Python 3.10 프로세스(main_py310.py)에서 실행됩니다.
        # Python 3.10 프로세스가 실행 중이 아니면 초기 연결이 실패할 수 있지만,
        # 재연결 옵션이 활성화되어 있어 자동으로 연결됩니다.
        bridge_thread = threading.Thread(target=bridge_client.connect, daemon=True)
        bridge_thread.start()
        logger.info("✅ 브리지 서버(Socket.IO) 연결 시도 중 (스레드 실행)")
        logger.info("   ℹ️  브리지 서버는 Python 3.10 프로세스에서 실행됩니다.")
        logger.info("   ℹ️  Python 3.10 프로세스를 실행하려면: python3.10 main_py310.py")
        
        try:
            # 무한 대기 (Ctrl+C로 종료)
            # 주기적으로 브리지 서버 연결 상태 확인 및 재연결 시도
            check_interval = 30  # 30초마다 확인
            last_check = 0
            
            while True:
                await asyncio.sleep(1)
                
                # 주기적으로 브리지 서버 연결 상태 확인 (로그 최소화)
                current_time = asyncio.get_event_loop().time()
                if current_time - last_check >= check_interval:
                    last_check = current_time
                    if bridge_client and not bridge_client.is_connected():
                        # 재연결 시도 (로그 없이)
                        bridge_client.ensure_connected(timeout=5.0)
        except KeyboardInterrupt:
            logger.info("🛑 종료 중...")
            await socketio_client.disconnect()
            logger.info("✅ 종료 완료")
    
    # 비동기 메인 함수 실행
    loop.run_until_complete(main_async())

if __name__ == "__main__":
    """
    라즈베리파이 메인 프로그램 (Python 3.13용)
    - Socket.IO 클라이언트 실행 (Python 3.13에서만 동작)
    - 브리지 서버 실행 (Python 3.10에서 오는 STT 결과 수신)
    - 브리지 클라이언트 실행 (STT 결과를 Socket.IO로 전송)
    
    실행 방법:
    1. Python 3.13에서 이 파일 실행: python3.13 main.py
    2. Python 3.10에서 main_py310.py 실행: python3.10 main_py310.py
    """
    # Socket.IO 클라이언트 및 브리지 클라이언트 실행
    # 참고: 브리지 서버는 Python 3.10에서 실행됩니다 (main_py310.py)
    run_socketio_client()