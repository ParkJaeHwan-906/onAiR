"""
Socket.IO 클라이언트
라즈베리파이에서 Socket.IO 서버에 연결하여 STT 결과를 전송합니다.
"""
import asyncio
import logging
import socketio
from config import settings

logger = logging.getLogger(__name__)

class SocketIOClient:
    """
    Socket.IO 클라이언트 래퍼 클래스
    라즈베리파이 디바이스로 등록하고 STT 결과를 전송합니다.
    """
    def __init__(self):
        self.server_url = settings.SOCKETIO_SERVER_URL
        self.sio = socketio.AsyncClient()
        self.connected = False
        self.sid = None
        
        # 이벤트 핸들러 등록
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Socket.IO 이벤트 핸들러 설정"""
        
        @self.sio.event
        async def connect():
            """서버 연결 성공 시 호출"""
            logger.info("✅ Socket.IO 서버 연결 성공")
            self.connected = True
            self.sid = self.sio.sid
            
            # 디바이스 등록
            await self.sio.emit("register_device", {"device": "raspi"})
            logger.info("🔗 라즈베리파이 디바이스 등록 요청 전송")
        
        @self.sio.event
        async def disconnect():
            """서버 연결 종료 시 호출"""
            logger.info("❌ Socket.IO 서버 연결 종료")
            self.connected = False
            self.sid = None
        
        @self.sio.on("server_message")
        async def handle_server_message(data):
            """서버로부터 메시지 수신"""
            msg = data.get("msg", "") if isinstance(data, dict) else str(data)
            logger.info(f"📨 서버 메시지: {msg}")
        
        @self.sio.on("pong")
        async def handle_pong(data):
            """서버로부터 pong 응답 수신"""
            logger.debug(f"🏓 Pong 수신: {data}")
    
    async def connect(self):
        """
        Socket.IO 서버에 연결합니다.
        
        Returns:
            bool: 연결 성공 여부
        """
        if self.connected:
            logger.warning("⚠️ 이미 Socket.IO 서버에 연결되어 있습니다.")
            return True
        
        try:
            logger.info(f"🔌 Socket.IO 서버 연결 시도: {self.server_url}")
            await self.sio.connect(self.server_url, wait_timeout=10)
            # connect 이벤트에서 connected가 True로 설정됨
            return self.connected
        except Exception as e:
            logger.error(f"❌ Socket.IO 서버 연결 실패: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Socket.IO 서버 연결 종료"""
        if self.sio and self.connected:
            try:
                await self.sio.disconnect()
                logger.info("🔌 Socket.IO 서버 연결 종료")
            except Exception as e:
                logger.error(f"❌ Socket.IO 연결 종료 오류: {e}")
            finally:
                self.connected = False
                self.sid = None
    
    async def emit_stt_result(self, stt_data: dict):
        """
        STT 결과를 Socket.IO 서버로 전송합니다.
        
        Args:
            stt_data: STT 결과 딕셔너리
                예: {"type": "final", "text": "안녕하세요", "confidence": 0.95}
        """
        if not self.connected:
            logger.warning("⚠️ Socket.IO 서버에 연결되어 있지 않습니다. STT 결과를 전송할 수 없습니다.")
            return False
        
        try:
            await self.sio.emit("stt_result", stt_data)
            logger.info(f"📤 STT 결과 전송: {stt_data.get('type', 'unknown')} - {stt_data.get('text', '')[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ STT 결과 전송 오류: {e}")
            return False
    
    def is_connected(self):
        """연결 상태 확인"""
        return self.connected
    
    async def wait(self):
        """Socket.IO 이벤트 루프 실행 (백그라운드 태스크용)"""
        await self.sio.wait()

