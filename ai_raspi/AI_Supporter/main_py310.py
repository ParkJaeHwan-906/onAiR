"""
라즈베리파이 메인 프로그램 (Python 3.10용)
- Wakeword 감지 (Python 3.10에서만 동작)
- 버퍼링/스트리밍 STT 실행 (Python 3.10에서만 동작)
"""

from socketio_handler.socket_handler import connect_to_fastapi
from audio.audio_streamer import AudioStreamer
from manager.manager import AudioModeManager
from stt.mic_stream import MicStream
from stt.stt_core import STTCore

import threading
import asyncio
import time
import sys

# 로깅 설정 (systemd에서도 보이도록)
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # stdout으로 출력 (systemd가 캡처)
        logging.StreamHandler(sys.stderr)  # stderr로도 출력
    ]
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("=" * 60)
        logger.info("🚀 AI Supporter 시작")
        logger.info("=" * 60)
        
        logger.info("1️⃣ 마이크 초기화 시작...")
        mic = MicStream()
        logger.info("✅ 마이크 초기화 완료")

        logger.info("2️⃣ 오디오 스트리머 초기화 시작...")
        audio_streamer = AudioStreamer(socketio_client=None)  
        logger.info("✅ 오디오 스트리머 초기화 완료")

        logger.info("3️⃣ 마이크 매니저 생성 시작...")
        manager = AudioModeManager(mic, audio_streamer)
        logger.info("✅ 마이크 매니저 생성 완료")

        logger.info("4️⃣ STT Core 초기화 시작 (Wakeword 모델 로드 중)...")
        stt_core = STTCore(manager)
        manager.stt_core = stt_core
        logger.info("✅ STT Core 초기화 완료 (Wakeword 모델 로드 완료)")
    except Exception as e:
        logger.error(f"❌ 초기화 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # STT Core 스레드 먼저 시작 (Socket.IO 연결과 독립적으로 실행)
    logger.info("5️⃣ STT Core 스레드 시작 중...")
    def run_stt_core():
        try:
            logger.info(f"🔄 STT Core 스레드 실행 시작 (스레드 ID: {threading.current_thread().ident})")
            stt_core.run()
        except Exception as e:
            logger.error(f"❌ STT Core 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
    
    stt_thread = threading.Thread(target=run_stt_core, daemon=True, name="STTCoreThread")
    stt_thread.start()
    logger.info(f"✅ STT Core 스레드 시작됨 (스레드 ID: {stt_thread.ident}, 이름: {stt_thread.name})")
    
    # 스레드가 실제로 시작될 때까지 잠시 대기
    time.sleep(0.2)
    logger.info(f"   STT 스레드 상태: alive={stt_thread.is_alive()}")

    # SocketIO 스레드 (별도 스레드에서 실행)
    logger.info("6️⃣ Socket.IO 스레드 시작 중...")
    def run_socketio():
        try:
            logger.info(f"🔄 Socket.IO 스레드 실행 시작 (스레드 ID: {threading.current_thread().ident})")
            # 새로운 이벤트 루프 생성 (별도 스레드에서 실행)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(connect_to_fastapi(manager))
        except Exception as e:
            logger.error(f"❌ Socket.IO 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
    
    socketio_thread = threading.Thread(target=run_socketio, daemon=True, name="SocketIOThread")
    socketio_thread.start()
    logger.info(f"✅ Socket.IO 스레드 시작됨 (스레드 ID: {socketio_thread.ident}, 이름: {socketio_thread.name})")
    time.sleep(0.2)
    logger.info(f"   Socket.IO 스레드 상태: alive={socketio_thread.is_alive()}")

    logger.info("=" * 60)
    logger.info("✅ 모든 초기화 완료 - Wakeword 감지 대기 중...")
    logger.info("=" * 60)

    # 메인 스레드는 대기 상태 유지
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 종료 신호 수신")
    except Exception as e:
        logger.error(f"❌ 메인 루프 오류: {e}")
        import traceback
        traceback.print_exc()