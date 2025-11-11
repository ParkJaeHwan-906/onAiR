import socketio
import logging
import asyncio

logger = logging.getLogger(__name__)

class SttBridgeClient:
    """
    STT 브리지 클라이언트 (Python 3.13)
    - Python 3.10 브리지 서버(Socket.IO)로부터 STT 결과를 수신
    - FastAPI Socket.IO 서버로 전달
    - Python 3.10으로 Streaming STT 시작 명령 전달
    """

    def __init__(self, bridge_url: str = "http://127.0.0.1:5050"):
        self.bridge_url = bridge_url
        # Socket.IO 클라이언트 생성 (재연결 옵션 포함)
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=1,
            reconnection_delay_max=5
        )
        self.socketio_fastapi_client = None  # 외부 Socket.IO 클라이언트 주입
        self.connected = False  # 연결 상태 추적
        
        # 연결 이벤트
        @self.sio.event
        def connect():
            self.connected = True
            logger.info(f"✅ STT 브리지 서버({self.bridge_url}) 연결 성공")

        @self.sio.event
        def disconnect():
            self.connected = False
            logger.warning("❌ STT 브리지 서버 연결 종료")
            # 자동 재연결 시도 (Socket.IO 클라이언트의 reconnection 옵션이 활성화되어 있음)
            logger.info("🔄 브리지 서버 재연결 시도 중...")

        # STT 결과 수신 이벤트
        @self.sio.on('stt_result')
        def on_stt_result(data):
            """When STT result is received from bridge server, send to FastAPI server."""
            logger.info("=" * 60)
            logger.info(f"📥 [단계 5] 브리지 클라이언트: STT 결과 수신")
            logger.info(f"   타입: {data.get('type')}, 텍스트: {data.get('text', '')[:50]}...")
            logger.info("=" * 60)
            
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
                            logger.info("📡 [단계 5-1] FastAPI 서버로 STT 결과 전송 시작...")
                            new_loop.run_until_complete(self.socketio_fastapi_client.emit_stt_result(data))
                            logger.info("=" * 60)
                            logger.info("✅ [단계 5 완료] FastAPI 서버로 STT 결과 전송 완료")
                            logger.info("=" * 60)
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
        
        # Wakeword 감지 이벤트 수신 (Python 3.10 → Python 3.13 → FastAPI)
        @self.sio.on('wakeword_detected')
        def on_wakeword_detected(data):
            """Wakeword 감지 이벤트를 FastAPI 서버로 전달"""
            logger.info("=" * 60)
            logger.info(f"📥 [단계 2-1] 브리지 클라이언트: Wakeword 감지 이벤트 수신")
            logger.info("=" * 60)
            
            # FastAPI 서버로 전송
            if self.socketio_fastapi_client and self.socketio_fastapi_client.is_connected():
                try:
                    def send_async():
                        """새 이벤트 루프에서 비동기 함수 실행"""
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            logger.info("📡 [단계 2-1] FastAPI 서버로 Wakeword 감지 이벤트 전송 시작...")
                            new_loop.run_until_complete(self.socketio_fastapi_client.emit_wakeword_detected())
                            logger.info("=" * 60)
                            logger.info("✅ [단계 2-1 완료] FastAPI 서버로 Wakeword 감지 이벤트 전송 완료")
                            logger.info("=" * 60)
                        finally:
                            new_loop.close()
                    
                    import threading
                    thread = threading.Thread(target=send_async, daemon=True)
                    thread.start()
                except Exception as e:
                    logger.error(f"❌ Failed to forward wakeword_detected to FastAPI: {e}")
            else:
                logger.warning("⚠️ FastAPI Socket.IO 클라이언트가 연결되지 않음, 전송 대기")

    def set_fastapi_socketio_client(self, socketio_client):
        """FastAPI 서버 Socket.IO 클라이언트 주입"""
        self.socketio_fastapi_client = socketio_client
        logger.info("FastAPI Socket.IO 클라이언트가 브리지에 연결됨")

    def is_connected(self):
        """브리지 서버 연결 상태 확인"""
        return self.connected and self.sio.connected

    def emit_start_streaming_stt(self, session_id: str):
        """
        Python 3.10으로 Streaming STT 시작 명령 전송
        
        Args:
            session_id: Clarify 세션 ID
        
        Returns:
            bool: 전송 성공 여부
        """
        # 연결 상태 확인
        if not self.is_connected():
            logger.warning("⚠️ 브리지 서버에 연결되어 있지 않습니다. 재연결 시도...")
            try:
                # 이미 연결 시도 중이면 기다림
                if self.sio.connected:
                    # 연결 상태만 업데이트
                    self.connected = True
                else:
                    # 재연결 시도
                    self.sio.connect(self.bridge_url)
                    # 연결 대기 (최대 2초)
                    import time
                    for _ in range(20):
                        if self.connected:
                            break
                        time.sleep(0.1)
            except Exception as e:
                logger.error(f"❌ 브리지 서버 재연결 실패: {e}")
                return False
        
        # 최종 연결 상태 확인
        if not self.is_connected():
            logger.error("=" * 60)
            logger.error("❌ 브리지 서버에 연결할 수 없습니다. Streaming STT 시작 명령을 전송할 수 없습니다.")
            logger.error("=" * 60)
            return False
        
        # Streaming STT 시작 명령 전송
        try:
            logger.info("=" * 60)
            logger.info(f"📤 [단계 12-1] 브리지 클라이언트: Streaming STT 시작 명령 전송")
            logger.info(f"   Session ID: {session_id}")
            logger.info("=" * 60)
            
            self.sio.emit('start_streaming_stt', {'session_id': session_id})
            
            logger.info("=" * 60)
            logger.info(f"✅ [단계 12-1] 브리지 클라이언트: Streaming STT 시작 명령 전송 완료")
            logger.info(f"   Session ID: {session_id}")
            logger.info("=" * 60)
            return True
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ [단계 12-1 실패] 브리지 서버로 Streaming STT 시작 명령 전송 실패: {e}")
            logger.error("=" * 60)
            self.connected = False  # 연결 상태 리셋
            return False

    def connect(self):
        """브리지 서버에 연결"""
        logger.info("=" * 60)
        logger.info("🔌 브리지 서버 연결 시도 중...")
        logger.info(f"   URL: {self.bridge_url}")
        logger.info("   ℹ️  브리지 서버는 Python 3.10 프로세스(main_py310.py)에서 실행됩니다.")
        logger.info("   ℹ️  Python 3.10 프로세스가 실행 중이 아니면 연결이 실패할 수 있습니다.")
        logger.info("   ℹ️  재연결 옵션이 활성화되어 있어, Python 3.10 프로세스가 시작되면 자동으로 연결됩니다.")
        logger.info("=" * 60)
        
        max_retries = 10
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"   연결 시도 {retry_count + 1}/{max_retries}...")
                self.sio.connect(self.bridge_url, wait_timeout=5)
                # 연결 성공 확인
                if self.sio.connected:
                    logger.info("=" * 60)
                    logger.info(f"✅ 브리지 서버 연결 성공! (시도 횟수: {retry_count + 1})")
                    logger.info("=" * 60)
                    self.sio.wait()  # 연결 유지
                    return
                else:
                    logger.warning(f"   연결 시도 실패 (연결 상태: {self.sio.connected})")
            except Exception as e:
                logger.warning(f"   연결 시도 {retry_count + 1} 실패: {e}")
            
            retry_count += 1
            if retry_count < max_retries:
                import time
                wait_time = min(2 ** retry_count, 10)  # 지수 백오프, 최대 10초
                logger.info(f"   {wait_time}초 후 재시도...")
                time.sleep(wait_time)
        
        # 최종 실패
        logger.error("=" * 60)
        logger.error(f"❌ 브리지 서버 연결 실패 (최대 시도 횟수: {max_retries})")
        logger.error("   확인 사항:")
        logger.error("   1. Python 3.10 프로세스(main_py310.py)가 실행 중인지 확인")
        logger.error("   2. 브리지 서버가 포트 5050에서 실행 중인지 확인: netstat -an | grep 5050")
        logger.error("   3. Python 3.10 프로세스를 실행하려면: python3.10 main_py310.py")
        logger.error("=" * 60)
        self.connected = False
        
        # 재연결을 위해 계속 시도 (재연결 옵션이 활성화되어 있음)
        try:
            logger.info("🔄 재연결 옵션으로 계속 재시도 중...")
            self.sio.wait()  # 재연결 대기
        except:
            pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bridge_client = SttBridgeClient()
    bridge_client.connect()
    