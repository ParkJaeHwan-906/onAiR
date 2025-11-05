"""
FastAPI 서버와 WebSocket 연결을 관리하는 클라이언트
스트리밍 모드에서 사용됩니다.
"""
import asyncio
import json
import logging
import uuid
import websockets
from config import settings

logger = logging.getLogger(__name__)

class FastApiWebSocketClient:
    def __init__(self):
        self.server_url = settings.FASTAPI_SERVER_URL.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_endpoint = settings.WS_CHAT_ENDPOINT if hasattr(settings, 'WS_CHAT_ENDPOINT') else "/ws/chat"
        self.websocket = None
        self.session_id = None
        self.lock = asyncio.Lock()

    async def connect(self):
        """FastAPI 서버와 WebSocket 연결"""
        try:
            url = f"{self.server_url}{self.ws_endpoint}"
            logger.info(f"🔌 FastAPI 서버 WebSocket 연결 시도: {url}")
            
            self.websocket = await websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info("✅ FastAPI 서버 WebSocket 연결 성공")
            
            # 세션 ID 생성
            self.session_id = str(uuid.uuid4())
            return True
        except Exception as e:
            logger.error(f"❌ FastAPI 서버 WebSocket 연결 실패: {e}")
            self.websocket = None
            return False

    async def disconnect(self):
        """WebSocket 연결 종료"""
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("🔌 FastAPI 서버 WebSocket 연결 종료")
            except Exception as e:
                logger.error(f"❌ WebSocket 종료 오류: {e}")
            finally:
                self.websocket = None
                self.session_id = None

    async def send_text(self, text: str):
        """
        STT 텍스트를 WebSocket으로 전송합니다.
        
        Args:
            text: STT로 인식된 텍스트
        
        Returns:
            bool: 전송 성공 여부
        """
        async with self.lock:
            if not self.websocket or self.websocket.closed:
                logger.warning("⚠️ WebSocket이 연결되지 않았습니다.")
                return False

            try:
                message = {
                    "type": "query",
                    "text": text,
                    "session_id": self.session_id
                }
                await self.websocket.send(json.dumps(message))
                logger.info(f"📤 FastAPI 서버로 전송: {text[:50]}...")
                return True
            except Exception as e:
                logger.error(f"❌ WebSocket 전송 오류: {e}")
                await self.disconnect()
                return False

    async def receive_response(self, timeout: float = 30.0):
        """
        FastAPI 서버로부터 응답을 수신합니다.
        
        Args:
            timeout: 타임아웃 (초)
        
        Returns:
            dict: 서버 응답 또는 None
        """
        if not self.websocket or self.websocket.closed:
            return None

        try:
            message = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=timeout
            )
            data = json.loads(message)
            
            # 세션 ID 업데이트
            if "session_id" in data:
                self.session_id = data["session_id"]
            
            logger.info(f"📥 FastAPI 서버 응답 수신: {data.get('type', 'unknown')}")
            return data
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ FastAPI 서버 응답 타임아웃")
            return None
        except Exception as e:
            logger.error(f"❌ WebSocket 수신 오류: {e}")
            await self.disconnect()
            return None

    async def listen_responses(self, callback):
        """
        FastAPI 서버로부터 지속적으로 응답을 수신합니다.
        
        Args:
            callback: 응답을 처리할 콜백 함수 (async)
        """
        if not self.websocket or self.websocket.closed:
            return

        try:
            while True:
                if self.websocket.closed:
                    break
                    
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=1.0
                    )
                    data = json.loads(message)
                    
                    # 세션 ID 업데이트
                    if "session_id" in data:
                        self.session_id = data["session_id"]
                    
                    await callback(data)
                except asyncio.TimeoutError:
                    # 타임아웃은 정상 (주기적 체크)
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.info("🔌 FastAPI 서버 WebSocket 연결 종료")
                    break
        except Exception as e:
            logger.error(f"❌ 응답 수신 루프 오류: {e}")
            await self.disconnect()

    def get_session_id(self):
        """현재 세션 ID를 반환합니다."""
        return self.session_id

    def reset_session(self):
        """세션을 초기화합니다."""
        self.session_id = None

