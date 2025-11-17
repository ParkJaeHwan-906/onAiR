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
        # reconnection_attempts=0이면 무한 재시도
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,  # 무한 재시도 (0 = 무제한)
            reconnection_delay=1,
            reconnection_delay_max=10  # 최대 10초 대기
        )
        self.socketio_fastapi_client = None  # 외부 Socket.IO 클라이언트 주입
        self.connected = False  # 연결 상태 추적
        self._reconnect_thread = None  # 재연결 스레드 추적
        
        # 연결 이벤트
        @self.sio.event
        def connect():
            self.connected = True
            # 로그 최소화: 정상 연결 시 로그 제거

        @self.sio.event
        def disconnect():
            self.connected = False
            logger.warning("⚠️ 브리지 서버 연결 종료 - 재연결 시도 중...")
            # 명시적 재연결 시도
            self._start_reconnect_thread()

        # STT 결과 수신 이벤트
        @self.sio.on('stt_result')
        def on_stt_result(data):
            """STT 결과를 FastAPI 서버로 전송"""
            if self.socketio_fastapi_client and self.socketio_fastapi_client.is_connected():
                try:
                    def send_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            new_loop.run_until_complete(self.socketio_fastapi_client.emit_stt_result(data))
                            # 로그 최소화: 정상 전송 시 로그 제거
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
            if self.socketio_fastapi_client and self.socketio_fastapi_client.is_connected():
                try:
                    send_success = [False]
                    
                    def send_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result = new_loop.run_until_complete(self.socketio_fastapi_client.emit_wakeword_detected())
                            send_success[0] = result
                            if not result:
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
        
        # Wakeword 대기 준비 완료 이벤트 수신 (Python 3.10 → Python 3.13 → FastAPI)
        @self.sio.on('wakeword_waiting_ready')
        def on_wakeword_waiting_ready(data):
            """Wakeword 대기 준비 완료 이벤트를 FastAPI 서버로 전달"""
            if self.socketio_fastapi_client and self.socketio_fastapi_client.is_connected():
                try:
                    send_success = [False]
                    
                    def send_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result = new_loop.run_until_complete(self.socketio_fastapi_client.emit_wakeword_waiting_ready())
                            send_success[0] = result
                            if not result:
                                logger.error("❌ Wakeword 대기 준비 완료 이벤트 전송 실패")
                        except Exception as e:
                            logger.error(f"❌ Wakeword 대기 준비 완료 이벤트 전송 오류: {e}")
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
                    logger.error(f"❌ Wakeword 대기 준비 완료 이벤트 전송 실패: {e}")
            else:
                logger.error("❌ FastAPI 클라이언트 미연결")
    
    def _start_reconnect_thread(self):
        """재연결 스레드 시작 (이미 실행 중이면 무시)"""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return  # 이미 재연결 시도 중
        
        import threading
        import time
        import socket
        
        def reconnect_loop():
            """재연결 루프 (백그라운드 스레드) - 빠른 재연결"""
            retry_count = 0
            max_retry_interval = 10  # 최대 10초 간격 (더 빠른 재연결)
            
            while not self.is_connected():
                try:
                    retry_count += 1
                    
                    # 먼저 서버가 준비되었는지 확인
                    server_ready = False
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(0.5)
                        result = sock.connect_ex(('127.0.0.1', 5050))
                        sock.close()
                        if result == 0:
                            server_ready = True
                    except:
                        pass
                    
                    # 서버가 준비되었으면 즉시 연결 시도
                    if server_ready:
                        try:
                            if not self.sio.connected:
                                self.sio.connect(self.bridge_url, wait_timeout=3)
                            if self.sio.connected:
                                self.connected = True
                                break
                        except:
                            pass
                    
                    # 지수 백오프, 최대 10초 (더 빠른 재연결)
                    wait_time = min(2 ** min(retry_count, 4), max_retry_interval)
                    time.sleep(wait_time)
                    
                except Exception as e:
                    # 오류 발생 시 1초 대기 후 재시도 (더 빠른 복구)
                    time.sleep(1)
        
        self._reconnect_thread = threading.Thread(target=reconnect_loop, daemon=True)
        self._reconnect_thread.start()

    def set_fastapi_socketio_client(self, socketio_client):
        """FastAPI 서버 Socket.IO 클라이언트 주입"""
        self.socketio_fastapi_client = socketio_client
        # 로그 최소화: 정상 설정 시 로그 제거

    def is_connected(self):
        """브리지 서버 연결 상태 확인"""
        return self.connected and self.sio.connected
    
    def ensure_connected(self, timeout=3.0):
        """
        브리지 서버 연결 상태 확인 및 필요시 재연결 시도 (빠른 재연결)
        
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
        
        # 서버가 준비되었는지 먼저 확인
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', 5050))
            sock.close()
            if result != 0:
                # 서버가 아직 준비되지 않음
                if not (self._reconnect_thread and self._reconnect_thread.is_alive()):
                    self._start_reconnect_thread()
                return False
        except:
            pass
        
        # 재연결 시도 (서버가 준비되었으면)
        try:
            if not self.sio.connected:
                self.sio.connect(self.bridge_url, wait_timeout=timeout)
                if self.sio.connected:
                    self.connected = True
                    return True
        except:
            pass
        
        # 재연결 스레드가 실행 중이 아니면 시작
        if not (self._reconnect_thread and self._reconnect_thread.is_alive()):
            self._start_reconnect_thread()
        
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
        """브리지 서버에 연결 (부팅 시 타이밍 이슈 대응)"""
        import time
        import socket
        
        # 먼저 브리지 서버가 준비될 때까지 대기 (최대 30초)
        max_wait_time = 30
        wait_start = time.time()
        server_ready = False
        
        while time.time() - wait_start < max_wait_time:
            try:
                # 포트가 열려있는지 확인
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', 5050))
                sock.close()
                if result == 0:
                    server_ready = True
                    break
            except:
                pass
            time.sleep(0.5)  # 0.5초마다 확인
        
        # 브리지 서버가 준비되었으면 즉시 연결 시도
        if server_ready:
            try:
                self.sio.connect(self.bridge_url, wait_timeout=5)
                if self.sio.connected:
                    self.connected = True
                    self.sio.wait()  # 연결 유지
                    return
            except:
                pass
        
        # 초기 연결 실패 시 빠른 재시도 (최대 20회, 1초 간격)
        max_retries = 20
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.sio.connect(self.bridge_url, wait_timeout=3)
                if self.sio.connected:
                    self.connected = True
                    self.sio.wait()  # 연결 유지
                    return
            except:
                pass
            
            retry_count += 1
            time.sleep(1)  # 1초 간격으로 빠르게 재시도
        
        # 최종 실패 시 재연결 스레드 시작 (백그라운드에서 계속 재시도)
        self.connected = False
        self._start_reconnect_thread()
        
        # 재연결을 위해 계속 시도 (재연결 옵션이 활성화되어 있음)
        try:
            self.sio.wait()  # 재연결 대기
        except:
            pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bridge_client = SttBridgeClient()
    bridge_client.connect()
    