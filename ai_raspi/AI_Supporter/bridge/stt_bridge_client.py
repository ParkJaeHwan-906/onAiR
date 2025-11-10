import socketio
import logging
import asyncio

logger = logging.getLogger(__name__)

class SttBridgeClient:
    """
    STT 브리지 클라이언트 (Python 3.13)
    - Python 3.10 브리지 서버(Socket.IO)로부터 STT 결과를 수신
    - FastAPI Socket.IO 서버로 전달
    """

    def __init__(self, bridge_url: str = "http://127.0.0.1:5050"):
        self.bridge_url = bridge_url
        self.sio = socketio.Client()
        self.socketio_fastapi_client = None  # 외부 Socket.IO 클라이언트 주입
        
        # 연결 이벤트
        @self.sio.event
        def connect():
            logger.info(f"✅ STT 브리지 서버({self.bridge_url}) 연결 성공")

        @self.sio.event
        def disconnect():
            logger.warning("❌ STT 브리지 서버 연결 종료")

        # STT 결과 수신 이벤트
        @self.sio.on('stt_result')
        def on_stt_result(data):
            """When STT result is received from bridge server, send to FastAPI server."""
            logger.info(f"📥 STT 결과 수신: {data.get('type')} - {data.get('text', '')[:50]}...")
            # FastAPI 서버로 전송
            if self.socketio_fastapi_client and self.socketio_fastapi_client.is_connected():
                try:
                    # SocketIOClient는 래퍼 클래스이므로 emit_stt_result() 메서드 사용
                    # 동기 스레드에서 비동기 함수 호출: 새 이벤트 루프 생성
                    def send_async():
                        """새 이벤트 루프에서 비동기 함수 실행"""
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            new_loop.run_until_complete(self.socketio_fastapi_client.emit_stt_result(data))
                            logger.info("📡 FastAPI 서버로 STT 결과 전송 완료")
                        finally:
                            new_loop.close()
                    
                    # 별도 스레드에서 실행 (이벤트 루프 충돌 방지)
                    import threading
                    thread = threading.Thread(target=send_async, daemon=True)
                    thread.start()
                except Exception as e:
                    logger.error(f"❌ Failed to forward STT result to FastAPI: {e}")
            else:
                logger.warning("⚠️ FastAPI Socket.IO 클라이언트가 연결되지 않음, 전송 대기")

    def set_fastapi_socketio_client(self, socketio_client):
        """FastAPI 서버 Socket.IO 클라이언트 주입"""
        self.socketio_fastapi_client = socketio_client
        logger.info("FastAPI Socket.IO 클라이언트가 브리지에 연결됨")

    def connect(self):
        """브리지 서버에 연결"""
        self.sio.connect(self.bridge_url)
        self.sio.wait()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bridge_client = SttBridgeClient()
    bridge_client.connect()
    