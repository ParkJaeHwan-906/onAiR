"""
Socket.IO 전송 관리자
Socket.IO 클라이언트를 통해 STT 결과를 전송하고, 모드 전환 명령을 받습니다.
"""
import asyncio
import logging
import json

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.socketio_client = None  # Socket.IO 클라이언트 인스턴스
        self.lock = asyncio.Lock()
        self.stt_mode = "buffered"  # "buffered" 또는 "streaming"
        self.mic_stream = None  # 마이크 스트림 인스턴스
        self.streaming_stt_instance = None  # Streaming STT 인스턴스 참조
        self.stop_streaming_sessions = set()  # 종료할 세션 ID 집합

    def set_socketio_client(self, socketio_client):
        """
        Socket.IO 클라이언트를 등록합니다.
        
        Args:
            socketio_client: SocketIOClient 인스턴스
        """
        self.socketio_client = socketio_client
        logger.info("✅ Socket.IO 클라이언트가 등록되었습니다.")

    def clear_socketio_client(self):
        """등록된 Socket.IO 클라이언트를 제거합니다."""
        self.socketio_client = None
        logger.info("Socket.IO 클라이언트가 제거되었습니다.")

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
    
    def set_streaming_stt_instance(self, streaming_stt_instance):
        """
        Streaming STT 인스턴스를 등록합니다.
        
        Args:
            streaming_stt_instance: GcpStreamingStt 인스턴스
        """
        self.streaming_stt_instance = streaming_stt_instance
        logger.info("✅ Streaming STT 인스턴스가 등록되었습니다.")
    
    def get_stop_streaming_session(self, session_id: str) -> bool:
        """세션 ID에 대한 종료 신호 확인 및 제거"""
        if session_id in self.stop_streaming_sessions:
            self.stop_streaming_sessions.remove(session_id)
            return True
        return False
    
    def add_stop_streaming_session(self, session_id: str):
        """종료할 세션 ID 추가"""
        self.stop_streaming_sessions.add(session_id)
        logger.info(f"🛑 Streaming STT 종료 신호 등록: session_id={session_id}")
        
        # Streaming STT 인스턴스에 직접 종료 신호 전달
        if self.streaming_stt_instance:
            self.streaming_stt_instance.stop_session(session_id)

    async def broadcast(self, message):
        """
        Socket.IO 클라이언트를 통해 STT 결과를 전송합니다.
        
        Args:
            message: 전송할 메시지 (딕셔너리 또는 JSON 문자열)
                딕셔너리 예: {"type": "final", "text": "안녕하세요", "confidence": 0.95}
                JSON 문자열 예: '{"type":"final","text":"안녕하세요","confidence":0.95}'
        """
        async with self.lock:
            if self.socketio_client is None:
                logger.warning("⚠️ Socket.IO 클라이언트가 등록되지 않았습니다. 메시지를 전송할 수 없습니다.")
                return
            
            if not self.socketio_client.is_connected():
                logger.warning("⚠️ Socket.IO 서버에 연결되어 있지 않습니다. 메시지를 전송할 수 없습니다.")
                return
            
            try:
                # 메시지 타입에 따라 처리
                if isinstance(message, dict):
                    # 이미 딕셔너리인 경우 그대로 사용
                    stt_data = message
                elif isinstance(message, str):
                    # JSON 문자열인 경우 파싱
                    try:
                        stt_data = json.loads(message)
                    except json.JSONDecodeError:
                        logger.error(f"❌ 잘못된 JSON 형식: {message}")
                        return
                else:
                    logger.error(f"❌ 지원하지 않는 메시지 타입: {type(message)}")
                    return
                
                # Socket.IO로 STT 결과 전송
                success = await self.socketio_client.emit_stt_result(stt_data)
                if not success:
                    logger.warning("⚠️ STT 결과 전송 실패")
            except Exception as e:
                logger.error(f"❌ Socket.IO 전송 오류: {e}")
