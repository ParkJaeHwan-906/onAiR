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
            """STT 결과를 FastAPI 서버로 전송"""
            logger.info(f"📥 STT 결과 수신: {data.get('type')} - {data.get('text', '')[:30]}...")
            
            if self.socketio_fastapi_client and self.socketio_fastapi_client.is_connected():
                try:
                    def send_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            new_loop.run_until_complete(self.socketio_fastapi_client.emit_stt_result(data))
                            logger.info("📤 STT 결과 전송 완료")
                        finally:
                            new_loop.close()
                    
                    import threading
                    thread = threading.Thread(target=send_async, daemon=True)
                    thread.start()
                except Exception as e:
                    logger.error(f"❌ STT 결과 전송 실패: {e}")
            else:
                logger.warning("⚠️ FastAPI 클라이언트 미연결")
        
        # Wakeword 감지 이벤트 수신 (Python 3.10 → Python 3.13 → FastAPI)
        @self.sio.on('wakeword_detected')
        def on_wakeword_detected(data):
            """Wakeword 감지 이벤트를 FastAPI 서버로 전달"""
            logger.info("📥 Wakeword 감지 이벤트 수신")
            
            if self.socketio_fastapi_client and self.socketio_fastapi_client.is_connected():
                try:
                    send_success = [False]
                    
                    def send_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result = new_loop.run_until_complete(self.socketio_fastapi_client.emit_wakeword_detected())
                            send_success[0] = result
                            if result:
                                logger.info("📤 Wakeword 감지 이벤트 전송 완료")
                            else:
                                logger.error("❌ Wakeword 감지 이벤트 전송 실패")
                        except Exception as e:
                            logger.error(f"❌ Wakeword 이벤트 전송 오류: {e}")
                            send_success[0] = False
                        finally:
                            new_loop.close()
                    
                    import threading
                    thread = threading.Thread(target=send_async, daemon=False)
                    thread.start()
                    thread.join(timeout=5)
                    
                    if not send_success[0]:
                        logger.error("❌ FastAPI 서버 응답 없음")
                except Exception as e:
                    logger.error(f"❌ Wakeword 이벤트 전송 실패: {e}")
            else:
                logger.error("❌ FastAPI 클라이언트 미연결")
        

    def set_fastapi_socketio_client(self, socketio_client):
        """FastAPI 서버 Socket.IO 클라이언트 주입"""
        self.socketio_fastapi_client = socketio_client
        logger.info("FastAPI Socket.IO 클라이언트가 브리지에 연결됨")

    def is_connected(self):
        """브리지 서버 연결 상태 확인"""
        return self.connected and self.sio.connected
    
    def ensure_connected(self, timeout=2.0):
        """
        브리지 서버 연결 상태 확인 및 필요시 재연결 시도
        
        Args:
            timeout: 재연결 대기 시간 (초)
        
        Returns:
            bool: 연결 성공 여부
        """
        if self.is_connected():
            return True
        
        # 이미 연결 시도 중이면 기다림
        if self.sio.connected:
            self.connected = True
            return True
        
        # 재연결 시도
        logger.warning("⚠️ 브리지 서버에 연결되어 있지 않습니다. 재연결 시도...")
        try:
            # 재연결 시도 (비동기적으로 처리)
            import threading
            reconnect_success = [False]
            
            def reconnect_bridge():
                try:
                    self.sio.connect(self.bridge_url, wait_timeout=5)
                    reconnect_success[0] = True
                except Exception as e:
                    logger.warning(f"⚠️ 브리지 서버 재연결 시도 중 오류: {e}")
            
            reconnect_thread = threading.Thread(target=reconnect_bridge, daemon=True)
            reconnect_thread.start()
            
            # 연결 대기
            import time
            reconnect_thread.join(timeout=timeout)
            
            # 연결 상태 확인
            if self.is_connected():
                logger.info("✅ 브리지 서버 재연결 성공!")
                return True
            else:
                logger.warning("⚠️ 브리지 서버 재연결 실패 (자동 재연결 대기 중...)")
                return False
        except Exception as e:
            logger.error(f"❌ 브리지 서버 재연결 실패: {e}")
            return False

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
    