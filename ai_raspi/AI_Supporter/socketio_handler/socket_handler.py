# socket_handler.py
import socketio
import logging
import asyncio
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SocketIOClient")

SERVER_URL = "https://onair.ai.kr"
SOCKET_PATH = "/ws"


class SocketIOClient:
    """
    라즈베리파이 → FastAPI Socket.IO 서버 양방향 통신 관리 클래스
    """
    def __init__(self, manager):
        self.manager = manager
        self.loop = None
        self._connected = False  # 연결 상태 추적
        # Async SocketIO Client 생성
        self.sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0  # 무한 재연결
        )

        # 이벤트 핸들러 등록
        self.sio.on("connect", self.on_connect)
        self.sio.on("disconnect", self.on_disconnect)
        self.sio.on("wakeword_audio_completed", self.on_wakeword_audio_completed)
        self.sio.on("handle_audio_stream", self.on_handle_audio_stream)
        self.sio.on("wakeword_start_waiting", self.on_wakeword_start_waiting)

    # ============================================================
    # 🔌 연결 이벤트
    # ============================================================
    async def on_connect(self):
        self._connected = True

        # 디바이스 등록 (raspi)
        await self.sio.emit("register_device", {"device": "raspi"})

        # Manager 에서 "socket_ready" 플래그 ON
        self.manager.set_socket_ready()

    async def on_disconnect(self):
        self._connected = False
        # 연결 해제 시 socket_ready 플래그도 해제
        self.manager.socket_ready.clear()

    # ============================================================
    # 📤 RTC/STT wakeword 감지 이벤트 전송
    # ============================================================
    async def emit_wakeword_detected(self):
        """
        STTCore → Manager → 여기로 호출됨
        """
        if not self.is_connected():
            return False
        
        try:
            await self.sio.emit("wakeword_detected", {})
            return True
        except Exception as e:
            logger.error(f"❌ wakeword_detected 전송 실패: {e}")
            return False

    async def emit_ai_support(self):
        """
        STTCore → Manager → 여기로 호출됨
        """
        if not self.is_connected():
            return False
        
        try:
            await self.sio.emit("stt_result", {
                "type": "final",
                "text": "AI 서포터 연결해줘",
                "confidence":"0.7",
                "session_id": ""
            })
            return True
        except Exception as e:
            logger.error(f"❌ stt_result 전송 실패: {e}")
            return False

    async def emit_connect_operator(self):
        """
        STTCore → Manager → 여기로 호출됨
        """
        if not self.is_connected():
            return False
        
        try:
            await self.sio.emit("stt_result", {
                "type": "final",
                "text": "OPERATOR 연결해줘",
                "confidence":"0.7",
                "session_id": ""
            })
            return True
        except Exception as e:
            logger.error(f"❌ stt_result 전송 실패: {e}")
            return False
    
    async def emit_audio_frame(self, timestamp, frame_bytes):
        try:
            await self.sio.emit(
                "audio_frame",
                {
                    "timestamp": timestamp,
                    "frame": frame_bytes
                }
            )
        except Exception as e:
            logger.error(f"❌ audio_frame emit 오류: {e}")
    #=============================================================
    async def on_wakeword_audio_completed(self, data):
        """
        FastAPI 서버에서 wakeword 오디오 처리가 완료되었음을 알림.
        """
        if hasattr(self.manager, "stt_core"):
            self.manager.stt_core.wakeword_audio_done.set()

    async def on_handle_audio_stream(self, data):
        """
        FastAPI 서버에서 RTC 오디오 스트림 제어 요청(start/stop)
        data = { "start": True } 또는 { "start": False }
        """
        if not hasattr(self.manager, "stt_core"):
            return

        # START 요청 (Operator 통신 연결 허가)
        if data.get("start") is True:
            self.manager.stt_core.operator_accept.set()

        # STOP 요청 (Operator 통신 종료)
        elif data.get("start") is False:
            self.manager.switch_to_stt()
            # 초기 상태로 복귀
            if hasattr(self.manager.stt_core, "reset_to_initial_state"):
                self.manager.stt_core.reset_to_initial_state()

    async def on_wakeword_start_waiting(self, data):
        """
        FastAPI 서버에서 wakeword 감지 대기 상태로 복귀 요청
        (서비스 메인 루프 종료 후 초기 상태로 복귀)
        """
        logger.info("=" * 60)
        logger.info("📩 wakeword_start_waiting 이벤트 수신 (초기 상태 복귀 요청)")
        logger.info("=" * 60)
        
        if not hasattr(self.manager, "stt_core"):
            logger.warning("⚠️ stt_core가 없습니다. 초기 상태 복귀 불가")
            return
        
        # 초기 상태로 복귀
        if hasattr(self.manager.stt_core, "reset_to_initial_state"):
            self.manager.stt_core.reset_to_initial_state()
        else:
            logger.warning("⚠️ reset_to_initial_state 메서드가 없습니다.")

    # ============================================================
    # 🔁 서버 연결 제어
    # ============================================================
    async def connect(self):
        """
        FastAPI Socket.IO 서버와의 연결을 시도.
        실패 시 3초마다 재시도.
        """
        while True:
            try:
                await self.sio.connect(
                    SERVER_URL,
                    socketio_path=SOCKET_PATH
                )
                self.loop = asyncio.get_running_loop()
                # on_connect 콜백에서 _connected가 True로 설정됨
                # 하지만 연결이 완료될 때까지 잠시 대기
                await asyncio.sleep(0.1)
                break
            except Exception as e:
                logger.error(f"❌ 연결 실패: {e} → 3초 후 재시도")
                self._connected = False
                await asyncio.sleep(3)

        # 연결 유지
        await self.sio.wait()
    
    def is_connected(self):
        """Socket.IO 서버 연결 상태 확인"""
        if not self.sio:
            return False
        # 내부 연결 상태 플래그와 sid 속성 모두 확인
        # sid가 있으면 연결된 상태
        has_sid = hasattr(self.sio, 'sid') and self.sio.sid is not None
        return self._connected and has_sid


# ==================================================================
# 📌 외부에서 호출하는 함수 (main.py 에서 사용)
# ==================================================================
async def connect_to_fastapi(manager):
    """
    main.py 에서 실행됨.
    - SocketIOClient 생성
    - Manager 에 socket_client 주입
    - AudioStreamer 에도 주입 (음성 스트리밍)
    - connect() 실행
    """
    socket_client = SocketIOClient(manager)

    # Manager 에 socket_client 연결
    manager.socketio_client = socket_client

    # RTC AudioStreamer 도 socket_client 필요하면 주입
    if manager.audio_streamer is not None:
        manager.audio_streamer.socketio_client = socket_client

    # 서버 연결 시작
    await socket_client.connect()
