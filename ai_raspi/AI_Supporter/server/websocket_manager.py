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
        self.service_completed = False  # 서비스 완료 플래그 (GPT-4o 답변 생성 및 TTS 완료 후 True)
        self.audio_streamer = None  # WebRTC 오디오 스트리머 인스턴스

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
    
    def set_service_completed(self, completed: bool = True):
        """
        서비스 완료 플래그 설정 (GPT-4o 답변 생성 및 TTS 완료 후 호출)
        
        Args:
            completed: 서비스 완료 여부 (기본값: True)
        """
        self.service_completed = completed
        logger.info(f"✅ 서비스 완료 플래그 설정: {completed}")
    
    def is_service_completed(self) -> bool:
        """서비스 완료 상태 확인"""
        return self.service_completed
    
    def reset_service_completed(self):
        """서비스 완료 플래그 리셋 (다음 서비스 대기)"""
        self.service_completed = False
        logger.info("🔄 서비스 완료 플래그 리셋")
    
    def set_audio_streamer(self, audio_streamer):
        """
        오디오 스트리머 인스턴스를 등록합니다.
        
        Args:
            audio_streamer: AudioStreamer 인스턴스
        """
        self.audio_streamer = audio_streamer
        logger.info("✅ 오디오 스트리머가 등록되었습니다.")
    
    def get_audio_streamer(self):
        """등록된 오디오 스트리머 인스턴스를 반환합니다."""
        return self.audio_streamer
