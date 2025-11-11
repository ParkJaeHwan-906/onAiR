"""
Socket.IO 클라이언트
라즈베리파이에서 Socket.IO 서버에 연결하여 STT 결과를 전송합니다.
"""
import asyncio
import logging
import socketio
import ssl
import aiohttp
from config import settings

logger = logging.getLogger(__name__)

class SocketIOClient:
    """
    Socket.IO 클라이언트 래퍼 클래스
    라즈베리파이 디바이스로 등록하고 STT 결과를 전송합니다.
    """
    def __init__(self, manager=None):
        """
        Args:
            manager: ConnectionManager 인스턴스 (선택사항, 종료 신호 처리용)
        """
        # FastAPI 서버 URL 사용 (Socket.IO 서버도 여기에 통합되어 있음)
        self.server_url = settings.FASTAPI_SERVER_URL
        
        # URL에서 호스트명과 포트 추출
        from urllib.parse import urlparse
        parsed_url = urlparse(self.server_url)
        self.hostname = parsed_url.hostname
        
        # HTTP인 경우 포트를 명시적으로 80으로 설정 (HTTPS 리다이렉트 방지)
        if parsed_url.scheme == 'http':
            # 포트가 명시되지 않았으면 80으로 설정
            if parsed_url.port is None:
                # URL에 포트를 명시적으로 추가하여 HTTP 강제
                if not self.server_url.endswith('/'):
                    self.server_url = f"{self.server_url}:80"
                else:
                    self.server_url = f"{self.server_url.rstrip('/')}:80/"
                parsed_url = urlparse(self.server_url)
            self.port = parsed_url.port or 80
        else:
            self.port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
        
        # 자동 재연결 설정
        # SSL 검증은 기본값 사용 (인증서 검증 활성화)
        self.sio = socketio.AsyncClient(
            reconnection=True,  # 자동 재연결 활성화
            reconnection_attempts=5,  # 최대 5회 재시도
            reconnection_delay=1,  # 1초 후 재시도
            reconnection_delay_max=5  # 최대 5초 대기
        )
        self.connected = False
        self.sid = None
        self.manager = manager  # ConnectionManager 참조
        
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
            logger.warning("❌ Socket.IO 서버 연결 종료 (자동 재연결 대기 중...)")
            self.connected = False
            self.sid = None
            # socketio.AsyncClient의 reconnection=True 설정으로 자동 재연결됨
        
        @self.sio.on("reconnect")
        async def handle_reconnect():
            """재연결 성공 시 호출"""
            logger.info("🔄 Socket.IO 서버 재연결 성공")
            self.connected = True
            self.sid = self.sio.sid
            # 디바이스 등록은 connect 이벤트에서 자동 처리됨
        
        @self.sio.on("reconnect_attempt")
        async def handle_reconnect_attempt():
            """재연결 시도 시 호출"""
            logger.info("🔄 Socket.IO 서버 재연결 시도 중...")
        
        @self.sio.on("reconnect_error")
        async def handle_reconnect_error(data):
            """재연결 실패 시 호출"""
            logger.error(f"❌ Socket.IO 재연결 실패: {data}")
        
        @self.sio.on("stop_streaming_stt")
        async def handle_stop_streaming_stt(data):
            """Streaming STT 종료 신호 수신"""
            session_id = data.get("session_id")
            reason = data.get("reason", "unknown")
            logger.info(f"🛑 Streaming STT 종료 신호 수신: session_id={session_id}, reason={reason}")
            
            # manager를 통해 종료 신호 전달
            if self.manager:
                self.manager.add_stop_streaming_session(session_id)
        
        @self.sio.on("cv_detection_failed")
        async def handle_cv_detection_failed(data):
            """CV 모델 오류 탐지 실패 이벤트 수신 (AI_SUPPORTER 분기)"""
            message = data.get("message", "")
            logger.info("=" * 60)
            logger.info(f"📩 [단계 11] 라즈베리파이(Python 3.13): cv_detection_failed 이벤트 수신")
            logger.info(f"   메시지: {message}")
            logger.info("=" * 60)
            
            # 라즈베리파이: 마이크 ON + Streaming STT 즉시 시작
            # 주의: Streaming STT는 Python 3.10 프로세스에서 실행되어야 함
            # Python 3.13에서는 인스턴스만 등록하고, 실제 실행은 Python 3.10에서 처리
            if self.manager:
                # STT 모드를 streaming으로 전환
                self.manager.set_stt_mode("streaming")
                
                # 세션 ID 생성 (Clarify 세션용)
                import uuid
                session_id = str(uuid.uuid4())
                
                logger.info("=" * 60)
                logger.info(f"📤 [단계 12-1] 브리지 서버로 Streaming STT 시작 명령 전송 준비")
                logger.info(f"   Session ID: {session_id}")
                logger.info("=" * 60)
                
                # 브리지 클라이언트를 통해 Python 3.10에 Streaming STT 시작 명령 전송
                # 브리지 클라이언트는 manager를 통해 접근 가능
                if hasattr(self.manager, 'bridge_client') and self.manager.bridge_client:
                    success = self.manager.bridge_client.emit_start_streaming_stt(session_id)
                    if success:
                        logger.info("=" * 60)
                        logger.info(f"✅ [단계 12-1 완료] 브리지 서버로 Streaming STT 시작 명령 전송 완료")
                        logger.info(f"   Session ID: {session_id}")
                        logger.info("=" * 60)
                    else:
                        logger.error("=" * 60)
                        logger.error(f"❌ [단계 12-1 실패] 브리지 서버로 Streaming STT 시작 명령 전송 실패")
                        logger.error(f"   Session ID: {session_id}")
                        logger.error("=" * 60)
                else:
                    logger.warning("=" * 60)
                    logger.warning("⚠️ 브리지 클라이언트가 등록되지 않았습니다. Streaming STT 시작 명령을 전송할 수 없습니다.")
                    logger.warning("=" * 60)
        
        @self.sio.on("control_raspi")
        async def handle_control_raspi(data):
            """라즈베리파이 제어 명령 수신 (모바일 → Socket.IO 서버 → 라즈베리파이)"""
            command = data.get("command", "")
            logger.info(f"📡 라즈베리파이 제어 명령 수신: command={command}")
            
            if command == "start_streaming_stt":
                # 스트리밍 STT 시작 명령
                logger.info("🎤 스트리밍 STT 시작 명령 수신")
                # manager를 통해 스트리밍 모드로 전환
                if self.manager:
                    self.manager.set_stt_mode("streaming")
                    # 마이크 활성화
                    mic = self.manager.get_mic_stream()
                    if mic and not mic.is_active():
                        mic.resume()
                        logger.info("🔊 마이크 ON (스트리밍 모드 시작)")
                    
                    # Streaming STT 인스턴스 가져오기
                    streaming_stt = self.manager.streaming_stt_instance
                    if streaming_stt:
                        # Socket.IO 클라이언트 설정
                        streaming_stt.socketio_client = self
                        
                        # 세션 ID 생성 (Clarify 세션용)
                        import uuid
                        session_id = str(uuid.uuid4())
                        logger.info(f"📤 Streaming STT 세션 즉시 시작 (session_id={session_id})")
                        
                        # 브로드캐스트 함수 (manager를 통해)
                        async def broadcaster(msg):
                            await self.manager.broadcast(msg)
                        
                        # Streaming STT 세션 시작 (별도 태스크로 실행)
                        try:
                            import asyncio
                            asyncio.create_task(
                                streaming_stt.run(mic, broadcaster=broadcaster, session_id=session_id)
                            )
                            logger.info("✅ Streaming STT 세션 시작 완료")
                        except Exception as e:
                            logger.error(f"❌ Streaming STT 세션 시작 실패: {e}")
                    else:
                        logger.error("❌ Streaming STT 인스턴스가 등록되지 않았습니다")
            
            elif command == "set_stt_mode":
                # STT 모드 설정 명령
                mode = data.get("mode", "buffered")
                logger.info(f"📝 STT 모드 설정 명령 수신: mode={mode}")
                if self.manager:
                    self.manager.set_stt_mode(mode)
                    # 스트리밍 모드로 전환 시 마이크 활성화
                    if mode == "streaming":
                        mic = self.manager.get_mic_stream()
                        if mic and not mic.is_active():
                            mic.resume()
                            logger.info("🔊 마이크 ON (스트리밍 모드 전환)")
            
            elif command == "notify_intent_done":
                # Intent 분기 완료 알림
                branch = data.get("branch", "")
                logger.info(f"✅ Intent 분기 완료 알림 수신: branch={branch}")
                # OPERATOR인 경우: 마이크 OFF 유지, STT 세션 종료 상태 유지
                # AI_SUPPORTER인 경우는 FastAPI 서버에서 cv_detection_failed 이벤트와 함께 처리됨
                if branch == "OPERATOR" and self.manager:
                    self.manager.set_stt_mode("buffered")
                    # 마이크는 OFF 상태 유지 (버퍼링 STT 후 이미 OFF됨)
                    # resume() 호출하지 않음
                    logger.info("🔇 OPERATOR 모드: 마이크 OFF 상태 유지, STT 세션 종료 상태 유지")
        
        @self.sio.on("server_message")
        async def handle_server_message(data):
            """서버로부터 메시지 수신"""
            msg = data.get("msg", "") if isinstance(data, dict) else str(data)
            logger.info(f"📨 서버 메시지: {msg}")
        
        @self.sio.on("pong")
        async def handle_pong(data):
            """서버로부터 pong 응답 수신"""
            logger.debug(f"🏓 Pong 수신: {data}")
        
        @self.sio.on("service_completed")
        async def handle_service_completed(data):
            """서비스 완료 이벤트 수신 (GPT-4o 답변 생성 및 TTS 완료 후)"""
            session_id = data.get("session_id", "")
            status = data.get("status", "")
            logger.info("=" * 60)
            logger.info(f"✅ [서비스 완료] service_completed 이벤트 수신")
            logger.info(f"   Session ID: {session_id}, Status: {status}")
            logger.info("=" * 60)
            
            # manager를 통해 wakeword 재활성화 신호 전달
            if self.manager:
                self.manager.set_service_completed(True)
                logger.info("🔊 Wakeword 재활성화 신호 전달 완료")
    
    def _check_server_certificate(self):
        """
        서버의 SSL 인증서 정보를 확인합니다.
        호스트명 불일치 문제 진단에 사용됩니다.
        """
        try:
            import socket
            context = ssl.create_default_context()
            with socket.create_connection((self.hostname, self.port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=self.hostname) as ssock:
                    cert = ssock.getpeercert()
                    logger.info(f"📜 서버 인증서 정보:")
                    logger.info(f"   주체: {cert.get('subject', 'N/A')}")
                    logger.info(f"   발급자: {cert.get('issuer', 'N/A')}")
                    if 'subjectAltName' in cert:
                        logger.info(f"   대체 이름: {cert['subjectAltName']}")
                    return cert
        except ssl.SSLCertVerificationError as e:
            logger.warning(f"⚠️ SSL 인증서 검증 실패: {e}")
            logger.warning(f"   서버의 인증서가 '{self.hostname}'에 대해 유효하지 않을 수 있습니다.")
            logger.warning(f"   서버 측에서 인증서를 올바르게 설정해야 합니다.")
            return None
        except Exception as e:
            logger.debug(f"인증서 확인 중 오류: {e}")
            return None
    
    async def connect(self):
        """
        Socket.IO 서버에 연결합니다.
        
        Returns:
            bool: 연결 성공 여부
        """
        if self.connected:
            logger.warning("⚠️ 이미 Socket.IO 서버에 연결되어 있습니다.")
            return True
        
        # HTTPS인 경우 인증서 정보 확인 (디버깅용)
        if self.server_url.startswith('https://'):
            cert_info = self._check_server_certificate()
            if cert_info is None:
                logger.warning("⚠️ 서버 인증서 확인 실패. 연결을 시도하지만 실패할 수 있습니다.")
        
        try:
            logger.info(f"🔌 Socket.IO 서버 연결 시도: {self.server_url} (경로: /ws)")
            # Socket.IO 경로는 /ws로 설정 (FastAPI 서버에 통합된 Socket.IO 서버)
            # SSL 인증서 검증 활성화 (기본값)
            await self.sio.connect(
                self.server_url,
                socketio_path="/ws",
                wait_timeout=10,
                transports=["polling", "websocket"]  # Polling 우선, WebSocket fallback
            )
            # connect 이벤트에서 connected가 True로 설정됨
            return self.connected
        except ssl.SSLCertVerificationError as e:
            logger.error(f"❌ SSL 인증서 검증 실패: {e}")
            logger.error(f"   서버 URL: {self.server_url}")
            logger.error(f"   호스트명: {self.hostname}")
            logger.error(f"   해결 방법:")
            logger.error(f"   1. 서버 측에서 인증서가 '{self.hostname}'에 대해 올바르게 설정되었는지 확인")
            logger.error(f"   2. 서버의 인증서가 만료되지 않았는지 확인")
            logger.error(f"   3. 서버의 인증서 체인이 올바른지 확인")
            self.connected = False
            return False
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
                Streaming STT의 경우: {"type": "final", "text": "...", "session_id": "uuid", ...}
        """
        if not self.connected:
            logger.warning("⚠️ Socket.IO 서버에 연결되어 있지 않습니다. 재연결 시도...")
            # 재연결 시도
            await self.connect()
            
            if not self.connected:
                logger.error("❌ 재연결 실패, STT 결과 전송 불가")
                return False
        
        try:
            await self.sio.emit("stt_result", stt_data)
            logger.info(f"📤 STT 결과 전송: {stt_data.get('type', 'unknown')} - {stt_data.get('text', '')[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ STT 결과 전송 오류: {e}")
            # 전송 실패 시 연결 상태 리셋
            self.connected = False
            return False
    
    async def emit_streaming_stt(self, text: str, msg_type: str = "final", confidence: float = None, session_id: str = None):
        """
        Streaming STT 결과를 Socket.IO 서버로 전송합니다.
        
        Args:
            text: STT로 인식된 텍스트
            msg_type: "final" | "interim" | "error" | "info"
            confidence: 신뢰도 (선택사항)
            session_id: Clarify 세션 ID (선택사항, 있으면 Streaming STT로 처리됨)
        
        Returns:
            bool: 전송 성공 여부
        """
        stt_data = {
            "type": msg_type,
            "text": text,
        }
        
        if confidence is not None:
            stt_data["confidence"] = confidence
        
        if session_id:
            stt_data["session_id"] = session_id
        
        return await self.emit_stt_result(stt_data)
    
    def is_connected(self):
        """연결 상태 확인"""
        return self.connected
    
    async def wait(self):
        """Socket.IO 이벤트 루프 실행 (백그라운드 태스크용)"""
        await self.sio.wait()

