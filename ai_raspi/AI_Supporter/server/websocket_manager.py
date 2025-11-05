"""
웹소켓 전송 관리자
이미 연결된 웹소켓을 통해 STT 결과를 전송하고, 모드 전환 명령을 받습니다.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.websocket = None
        self.lock = asyncio.Lock()
        self.stt_mode = "buffered"  # "buffered" 또는 "streaming"
        self.mic_stream = None  # 마이크 스트림 인스턴스

    def set_websocket(self, websocket):
        """
        외부에서 연결된 웹소켓을 등록합니다.
        
        Args:
            websocket: 이미 연결된 웹소켓 객체 (send_text 메서드를 가진 객체)
        """
        self.websocket = websocket
        logger.info("✅ 웹소켓이 등록되었습니다.")

    def clear_websocket(self):
        """등록된 웹소켓을 제거합니다."""
        self.websocket = None
        logger.info("웹소켓이 제거되었습니다.")

    def set_stt_mode(self, mode: str):
        """
        STT 모드를 변경합니다.
        
        Args:
            mode: "buffered" 또는 "streaming"
        """
        if mode in ["buffered", "streaming"]:
            self.stt_mode = mode
            logger.info(f"✅ STT 모드 변경: {mode}")
        else:
            logger.warning(f"⚠️ 잘못된 STT 모드: {mode}")

    def get_stt_mode(self) -> str:
        """현재 STT 모드를 반환합니다."""
        return self.stt_mode

    def set_mic_stream(self, mic_stream):
        """
        마이크 스트림 인스턴스를 등록합니다.
        
        Args:
            mic_stream: MicStream 인스턴스
        """
        self.mic_stream = mic_stream
        logger.info("✅ 마이크 스트림이 등록되었습니다.")

    def get_mic_stream(self):
        """등록된 마이크 스트림 인스턴스를 반환합니다."""
        return self.mic_stream

    async def broadcast(self, message: str):
        """
        등록된 웹소켓을 통해 STT 결과를 전송합니다.
        
        Args:
            message: 전송할 JSON 문자열 메시지
        """
        async with self.lock:
            if self.websocket is None:
                logger.warning("⚠️ 웹소켓이 등록되지 않았습니다. 메시지를 전송할 수 없습니다.")
                return
            
            try:
                # 웹소켓 객체가 send_text 메서드를 가지는 경우
                if hasattr(self.websocket, 'send_text'):
                    await self.websocket.send_text(message)
                # 일반적인 웹소켓 객체인 경우
                elif hasattr(self.websocket, 'send'):
                    await self.websocket.send(message)
                else:
                    logger.error("❌ 웹소켓 객체에 전송 메서드를 찾을 수 없습니다.")
            except Exception as e:
                logger.error(f"❌ 웹소켓 전송 오류: {e}")
                self.websocket = None
