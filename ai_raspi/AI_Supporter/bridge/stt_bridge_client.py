import socketio
import logging

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
            logger.info(f"📥 STT 결과 수신: {data.get('type')} - {data.get('text', '')[:50]}...")
            # FastAPI 서버로 전송
            if self.socketio_fastapi_client and self.socketio_fastapi_client.is_connected():
                self.socketio_fastapi_client.emit('stt_result', data)
                logger.info("📡 FastAPI 서버로 STT 결과 전송 완료")
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
    