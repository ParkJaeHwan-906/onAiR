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
    
    # 브리지 클라이언트 초기화
    bridge_client = SttBridgeClient()
    bridge_client.set_socketio_client(socketio_client)
    
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
        
        # 브리지 서버 연결 확인
        bridge_ok = await bridge_client.check_bridge_server()
        if not bridge_ok:
            logger.warning("⚠️ 브리지 서버가 실행되지 않았습니다.")
            logger.warning("   Python 3.10에서 브리지 서버를 실행했는지 확인하세요.")
            return
        
        # 브리지 클라이언트 시작 (STT 결과 폴링)
        await bridge_client.start()
        
        logger.info("🚀 Socket.IO 클라이언트 및 브리지 클라이언트 실행 중...")
        logger.info("   Python 3.10에서 오는 STT 결과를 Socket.IO로 전송합니다.")
        
        try:
            # 무한 대기 (Ctrl+C로 종료)
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 종료 중...")
            await bridge_client.stop()
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
