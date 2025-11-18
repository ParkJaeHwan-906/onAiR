"""
라즈베리파이 메인 프로그램 (Python 3.10용)
- Wakeword 감지 (Python 3.10에서만 동작)
- 버퍼링/스트리밍 STT 실행 (Python 3.10에서만 동작)
- 브리지 서버 실행 (STT 결과를 Python 3.13으로 전달)
- STT 결과를 브리지 서버로 전송
"""
import threading
import asyncio
import logging
import os
import time
import subprocess
import fcntl
from stt.mic_stream import MicStream
from stt.gcp_stt_buffered import GcpBufferedStt
from stt.gcp_stt_stream import GcpStreamingStt
from stt.wakeword_hook import wait_for_wakeword, init_wakeword_detector, stop_wakeword_detector
from bridge.stt_bridge_server import (
    run_server, send_stt_result, set_start_streaming_stt_callback, 
    set_service_completed_callback, send_wakeword_detected, 
    send_wakeword_waiting_ready,
    set_wakeword_audio_completed_callback,
    set_wakeword_start_waiting_callback, set_mic_off_callback, set_mic_on_callback,
    set_mic_release_callback, set_mic_acquire_callback, set_stop_buffered_stt_callback
)
from server.app import manager  # ConnectionManager 인스턴스
from config import settings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 자동 모드 플래그 (전역 변수)
auto_mode_enabled = False

# ========================================
# 디버그 모드 제거됨 - 자동 진행
# ========================================

def wait_for_next_step_sync(step_name: str, step_number: str = ""):
    """디버그 모드 제거됨 - 즉시 진행"""
    pass


def run_stt_loop():
    """
    메인 STT 루프 (Python 3.10에서 실행)
    설계에 따른 동작 흐름:
    ① 대기 (마이크 ON, Wakeword 감지 중)
    ② Wakeword 감지
    ③ 버퍼링 방식 STT 실행 (마이크 ON 상태)
    ④ 텍스트 전송 → 마이크 OFF (Intent 분류 중간)
    ⑤ Intent 분류 완료 후 모드 전환 (Python 3.13에서 처리)
    ⑥ 스트리밍 방식 STT 시작 (마이크 ON)
    ⑦ 서비스 종료 → STT 세션 OFF (마이크는 계속 ON)
    ⑧ 대기 복귀 (마이크 ON, 다음 Wakeword 대기)
    """
    # 브리지 서버를 별도 스레드에서 실행 (재시도 포함)
    bridge_thread = None
    max_bridge_retries = 3
    bridge_retry_delay = 1.0
    
    for bridge_attempt in range(max_bridge_retries):
        try:
            # 포트 점유 확인 및 해제 시도
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', 5050))
            sock.close()
            
            if result == 0:
                # 포트가 이미 사용 중인 경우
                if bridge_attempt < max_bridge_retries - 1:
                    logger.warning(f"⚠️ 포트 5050이 이미 사용 중입니다. 기존 프로세스 종료 시도 중... ({bridge_attempt + 1}/{max_bridge_retries})")
                    try:
                        # 기존 프로세스 종료 시도
                        subprocess.run(['pkill', '-f', 'stt_bridge_server'], timeout=2, check=False)
                        time.sleep(1)
                    except Exception:
                        pass
                    continue
            
            # 브리지 서버 시작
            bridge_thread = threading.Thread(
                target=run_server,
                args=('127.0.0.1', 5050),
                daemon=True
            )
            bridge_thread.start()
            logger.info("🚀 브리지 서버 시작 (포트 5050)")
            
            # 브리지 서버가 시작될 때까지 대기 (최대 3초)
            max_wait_time = 3
            wait_start = time.time()
            server_ready = False
            
            while time.time() - wait_start < max_wait_time:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    result = sock.connect_ex(('127.0.0.1', 5050))
                    sock.close()
                    if result == 0:
                        server_ready = True
                        break
                except Exception:
                    pass
                time.sleep(0.2)
            
            if server_ready:
                logger.info("✅ 브리지 서버 시작 확인 완료")
                break  # 성공 시 루프 종료
            else:
                if bridge_attempt < max_bridge_retries - 1:
                    logger.warning(f"⚠️ 브리지 서버 포트 연결 확인 실패, 재시도 중... ({bridge_attempt + 1}/{max_bridge_retries})")
                    time.sleep(bridge_retry_delay)
                    continue
                else:
                    logger.warning("⚠️ 브리지 서버 포트 연결 확인 실패. 서버가 시작되지 않았을 수 있습니다.")
                    break  # 마지막 시도 실패해도 계속 진행 (메인 로직 방해 최소화)
                    
        except Exception as e:
            if bridge_attempt < max_bridge_retries - 1:
                logger.warning(f"⚠️ 브리지 서버 시작 실패, 재시도 중... ({bridge_attempt + 1}/{max_bridge_retries}): {e}")
                time.sleep(bridge_retry_delay)
                continue
            else:
                logger.error("=" * 60)
                logger.error(f"❌ 브리지 서버 시작 실패 (최종): {e}")
                logger.error("   해결 방법:")
                logger.error("   1. 포트 5050을 사용 중인 프로세스 확인: sudo lsof -i :5050")
                logger.error("   2. 프로세스 종료: sudo kill -9 <PID>")
                logger.error("   3. 또는 모든 main_py310.py 프로세스 종료: pkill -f main_py310.py")
                logger.error("=" * 60)
                # 마지막 시도 실패해도 프로그램 계속 실행 (메인 로직 방해 최소화)
                logger.warning("⚠️ 브리지 서버 없이 계속 진행합니다. 일부 기능이 제한될 수 있습니다.")
                break
    
    # WebRTC 프로세스 확인 (마이크 점유 확인)
    webrtc_pids = []
    try:
        result = subprocess.run(['pgrep', '-f', 'socket_manager.py'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            webrtc_pids = [pid for pid in pids if pid]
    except Exception as e:
        logger.warning(f"⚠️ WebRTC 프로세스 확인 실패: {e}")
    
    # 주의: 마이크 점유 확인은 MicStream.start()에서 직접 수행됩니다.
    # MicStream.start()는 자동으로 장치를 선택하고 마이크를 열며,
    # WebRTC 프로세스가 마이크를 점유하고 있으면 적절한 오류 메시지를 출력합니다.
    
    # 마이크 초기화 및 시작 (재시도 포함)
    mic = MicStream()
    wakeword_detector = init_wakeword_detector()
    
    if wakeword_detector and wakeword_detector.interpreter is not None:
        mic.set_wakeword_callback(wakeword_detector.process_audio_chunk)
    
    max_mic_retries = 3
    mic_retry_delay = 1.0
    
    for mic_attempt in range(max_mic_retries):
        try:
            mic.start()
            logger.info("🔊 마이크 ON")
            break  # 성공 시 루프 종료
        except Exception as e:
            if mic_attempt < max_mic_retries - 1:
                logger.warning(f"⚠️ 마이크 시작 실패, 재시도 중... ({mic_attempt + 1}/{max_mic_retries}): {e}")
                time.sleep(mic_retry_delay)
                # 마이크 재초기화 시도
                try:
                    mic.stop()
                except Exception:
                    pass
                mic = MicStream()
                if wakeword_detector and wakeword_detector.interpreter is not None:
                    mic.set_wakeword_callback(wakeword_detector.process_audio_chunk)
                continue
            else:
                logger.error(f"❌ 마이크 시작 실패 (최종): {e}")
                raise RuntimeError("마이크를 사용할 수 없습니다.") from e
    
    # STT 인스턴스 생성
    buffered_stt = GcpBufferedStt()
    streaming_stt = GcpStreamingStt()
    
    # 버퍼링 STT 실행 중 플래그 (중지 가능하도록)
    buffered_stt_running = {"running": False}
    
    async def broadcast(msg):
        """STT 결과를 브리지 서버(Socket.IO)로 전송 (재시도 포함)"""
        max_retries = 2  # 최대 2회 재시도 (메인 로직 방해 최소화)
        retry_delay = 0.5  # 0.5초 간격 (빠른 재시도)
        
        for attempt in range(max_retries):
            success = send_stt_result(msg)
            if success:
                return  # 전송 성공
            
            # 마지막 시도가 아니면 재시도
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ 브리지 서버 연결 실패, 재시도 중... ({attempt + 1}/{max_retries})")
                await asyncio.sleep(retry_delay)
        
        # 모든 재시도 실패 시 예외 발생하여 wakeword 대기 상태로 복귀
        raise ConnectionError("브리지 클라이언트 연결 실패 - STT 결과 전송 불가")
    
    async def stt_session():
        """STT 세션 실행 (모드에 따라 버퍼링/스트리밍 선택)"""
        try:
            # 모드 확인 (기본값: buffered)
            mode = "buffered"  # Python 3.13에서 모드 전환 명령을 받을 수 있도록 확장 가능
            
            if mode == "buffered":
                # 버퍼링 방식: 3~5초 수집 후 일괄 처리 (분기처리 이전)
                # 마이크는 이미 켜져있음
                logger.info("🎙️ 버퍼링 STT 세션 시작")
                buffered_stt_running["running"] = True
                try:
                    await buffered_stt.run(mic, broadcast)
                    logger.info("✅ 버퍼링 STT 세션 완료")
                except Exception as e:
                    logger.error(f"❌ 버퍼링 STT 실행 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    raise  # 상위로 예외 전파
                finally:
                    buffered_stt_running["running"] = False
                # 버퍼링 STT 후 텍스트 전송 완료
                # 주의: 마이크는 계속 ON 상태로 유지됨
            else:
                # 스트리밍 방식: 실시간 인식 (분기처리 이후)
                logger.info("🎤 스트리밍 모드 시작 (실시간 음성 인식)")
                # 주의: 마이크는 항상 ON 상태로 유지되므로 별도의 활성화 불필요
                
                # 세션 ID 생성 (Clarify 세션용)
                import uuid
                session_id = str(uuid.uuid4())
                
                logger.info(f"📤 브리지 서버를 통해 Streaming STT 전송 시작 (session_id={session_id})")
                try:
                    await streaming_stt.run(mic, broadcaster=broadcast, session_id=session_id)
                except Exception as e:
                    logger.error(f"❌ 스트리밍 STT 실행 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    raise  # 상위로 예외 전파
                # 스트리밍 종료 후 마이크는 켜둠 (다음 Wakeword 대기)
                logger.info("🟢 스트리밍 모드 종료, 마이크는 계속 ON")
                
        except Exception as e:
            logger.error(f"❌ STT 세션 오류: {e}")
            import traceback
            traceback.print_exc()
            # 에러 발생 시에도 마이크는 켜둠 (다음 Wakeword 대기를 위해)
            if not mic.is_active():
                mic.resume()
            raise  # 상위로 예외 전파하여 wakeword 대기 상태로 복귀
    
    # 이벤트 루프 생성
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Streaming STT 시작 함수 (Python 3.13에서 호출될 수 있음)
    # 주의: loop가 정의된 후에 등록해야 함
    def start_streaming_stt(session_id: str):
        """브리지 서버를 통해 받은 Streaming STT 시작 명령 처리"""
        logger.info("=" * 60)
        logger.info(f"📥 [라즈베리파이] Streaming STT 시작 명령 수신")
        logger.info(f"   Session ID: {session_id}")
        logger.info("=" * 60)
        
        # 마이크 활성화 (버퍼링 STT 후 OFF되었을 수 있음)
        if not mic.is_active():
            mic.resume()
            logger.info("=" * 60)
            logger.info(f"🔊 [라즈베리파이] 마이크 활성화 (Streaming STT 시작)")
            logger.info("=" * 60)
        
        # Streaming STT 세션 시작 (별도 태스크로 실행)
        async def run_streaming():
            try:
                logger.info("=" * 60)
                logger.info(f"🎤 [라즈베리파이] Streaming STT 세션 시작")
                logger.info(f"   Session ID: {session_id}")
                logger.info(f"   💡 사용자가 말하면 침묵 1.5초 후 한 문장으로 인식하여 FastAPI로 전송")
                logger.info("=" * 60)
                await streaming_stt.run(mic, broadcaster=broadcast, session_id=session_id)
                logger.info("=" * 60)
                logger.info(f"✅ [라즈베리파이] Streaming STT 세션 종료")
                logger.info("=" * 60)
            except Exception as e:
                logger.error("=" * 60)
                logger.error(f"❌ [라즈베리파이] Streaming STT 세션 오류: {e}")
                logger.error("=" * 60)
        
        # 이벤트 루프에서 실행
        loop.call_soon_threadsafe(lambda: asyncio.create_task(run_streaming()))
    
    # 브리지 서버에 Streaming STT 시작 콜백 등록
    set_start_streaming_stt_callback(start_streaming_stt)
    
    # 버퍼링 STT 세션 종료 콜백 등록
    def handle_stop_buffered_stt(reason: str):
        """버퍼링 STT 세션 종료 처리"""
        # 로그 최소화: 정상 처리 시 로그 제거
        pass
    
    set_stop_buffered_stt_callback(handle_stop_buffered_stt)
    
    # Wakeword 감지 대기 시작 콜백 등록
    def handle_wakeword_start_waiting():
        """Wakeword 감지 대기 시작 처리 (CV 탐지 성공 시 FastAPI에서 wakeword_start_waiting 이벤트로 호출)"""
        # 서비스 진행 중 플래그 해제 (CV 탐지 성공 시 정상 완료이므로 새로운 wakeword 감지 허용)
        service_in_progress["in_progress"] = False
        
        # 마이크 상태 확인 및 활성화
        if not mic.is_active():
            mic.resume()
        
        # Wakeword 감지기 재개
        if wakeword_detector and wakeword_detector.interpreter is not None:
            wakeword_detector.resume()
            mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
        
        # 버퍼링 STT 실행 상태 리셋
        buffered_stt_running["running"] = False
        
        # CV 탐지 성공 시 wakeword_start_waiting 이벤트로 서비스 완료 처리
        # (메인 루프가 service_completed 이벤트를 기다리는 동안 이 이벤트가 오는 경우)
        service_completed_flag_global["completed"] = True
        
        # FastAPI로 Wakeword 대기 준비 완료 이벤트 전송 (YOLO 서버 API 요청 트리거용)
        try:
            send_wakeword_waiting_ready()
            # 로그 최소화: 정상 전송 시 로그 제거
        except Exception as e:
            # 로그 최소화: 무시 가능한 오류는 로그 제거
            pass
    
    set_wakeword_start_waiting_callback(handle_wakeword_start_waiting)
    
    # STT 목적 음성 수집 중지 콜백 등록
    def handle_mic_off():
        """STT 목적 음성 수집 중지 처리"""
        # 로그 최소화: 정상 처리 시 로그 제거
        mic.pause()
    
    set_mic_off_callback(handle_mic_off)
    
    # STT 목적 음성 수집 재개 콜백 등록
    def handle_mic_on():
        """STT 목적 음성 수집 재개 처리"""
        # 로그 최소화: 정상 처리 시 로그 제거
        if not mic.is_active():
            mic.resume()
    
    set_mic_on_callback(handle_mic_on)
    
    # 마이크 장치 해제 콜백 등록 (WebRTC 프로세스가 마이크를 사용할 수 있도록)
    def handle_mic_release():
        """마이크 장치 해제 처리 (WebRTC 프로세스가 마이크를 사용할 수 있도록)"""
        # Wakeword 감지기 일시 중지 (마이크 해제 중에는 wakeword 감지 불가)
        if wakeword_detector and wakeword_detector.interpreter is not None:
            wakeword_detector.pause()
            mic.disable_wakeword_callback()  # Wakeword 콜백 비활성화
        
        mic.release()  # 마이크 스트림을 완전히 닫아서 장치를 해제
        # 로그 최소화: 정상 처리 시 로그 제거
    
    set_mic_release_callback(handle_mic_release)
    
    # 서비스 완료 플래그 (전역 변수로 관리하여 handle_mic_acquire에서 접근 가능하도록)
    service_completed_flag_global = {"completed": False}
    
    # 서비스 진행 중 플래그 (서비스 진행 중에는 wakeword 감지 비활성화)
    service_in_progress = {"in_progress": False}
    
    # 마이크 장치 재점유 콜백 등록 (WebRTC 프로세스가 마이크를 해제한 후)
    def handle_mic_acquire():
        """마이크 장치 재점유 처리 (WebRTC 프로세스가 마이크를 해제한 후)"""
        # 서비스 진행 중 플래그 해제 (통신 종료 시 정상 완료이므로 새로운 wakeword 감지 허용)
        service_in_progress["in_progress"] = False
        
        mic.acquire()  # 마이크 스트림을 다시 시작해서 장치를 재점유
        # 재점유 후 논리적으로도 ON 상태로 설정
        if mic.is_paused:
            mic.resume()
        
        # 마이크 재점유 후 Wakeword 감지 대기 상태로 복귀
        if wakeword_detector and wakeword_detector.interpreter is not None:
            wakeword_detector.resume()  # Wakeword 감지기 재개
            mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
        else:
            logger.warning("⚠️ Wakeword 감지기가 초기화되지 않았습니다")
        
        # 버퍼링 STT 실행 상태 리셋 (혹시 실행 중이었다면)
        buffered_stt_running["running"] = False
        
        # Operator 분기에서 통신 종료 시 service_completed 플래그를 True로 설정
        # (메인 루프가 service_completed 이벤트를 기다리는 동안 통신이 종료된 경우)
        service_completed_flag_global["completed"] = True
        
        # FastAPI로 Wakeword 대기 준비 완료 이벤트 전송 (YOLO 서버 API 요청 트리거용)
        try:
            send_wakeword_waiting_ready()
            # 로그 최소화: 정상 전송 시 로그 제거
        except Exception as e:
            # 로그 최소화: 무시 가능한 오류는 로그 제거
            pass
    
    set_mic_acquire_callback(handle_mic_acquire)
    
    logger.info("🎧 STT 루프 시작 (Wakeword 감지 대기 중)")
    
    def reset_to_wakeword_waiting(reason: str = "알 수 없는 오류", allow_new_service: bool = True):
        """
        Wakeword 감지 대기 상태로 복귀
        
        Args:
            reason: 복귀 이유
            allow_new_service: 새로운 서비스 시작 허용 여부 (기본값: True)
                              False인 경우 일정 시간(2초) 대기 후 플래그 해제하여 서비스 겹침 방지
        """
        # Wakeword 감지 대기 상태로 복귀 로그 (항상 출력)
        logger.info(f"🔄 Wakeword 감지 대기 중 상태로 복귀: {reason}")
        
        try:
            # 서비스 진행 중 플래그 해제 여부 결정
            # - 정상 완료 시: allow_new_service=True로 호출하여 즉시 플래그 해제
            # - 예외 발생 시: allow_new_service=False로 호출하여 2초 대기 후 플래그 해제 (서비스 겹침 방지)
            if allow_new_service:
                service_in_progress["in_progress"] = False
            else:
                # 예외 발생 시 일정 시간 대기 후 플래그 해제 (이전 서비스가 완전히 종료될 시간 확보)
                def delayed_flag_reset():
                    time.sleep(2.0)  # 2초 대기
                    service_in_progress["in_progress"] = False
                    # 대기 후 wakeword 감지기 재개
                    if wakeword_detector and wakeword_detector.interpreter is not None:
                        wakeword_detector.resume()
                        mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
                    # FastAPI로 Wakeword 대기 준비 완료 이벤트 전송
                    try:
                        send_wakeword_waiting_ready()
                    except Exception as e:
                        pass
                
                # 별도 스레드에서 지연 해제 실행 (비동기)
                import threading
                reset_thread = threading.Thread(target=delayed_flag_reset, daemon=True)
                reset_thread.start()
            
            # 마이크 상태 확인 및 활성화
            if not mic.is_active():
                mic.resume()
            
            # Wakeword 감지기 재개 (allow_new_service=True인 경우에만 즉시 재개)
            if allow_new_service:
                if wakeword_detector and wakeword_detector.interpreter is not None:
                    wakeword_detector.resume()
                    mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
            else:
                # 예외 발생 시 wakeword 감지기는 일시 중지 상태 유지 (2초 후 별도 스레드에서 재개)
                if wakeword_detector:
                    wakeword_detector.pause()
                mic.disable_wakeword_callback()
            
            # 버퍼링 STT 실행 상태 리셋
            buffered_stt_running["running"] = False
            
            # FastAPI로 Wakeword 대기 준비 완료 이벤트 전송 (YOLO 서버 API 요청 트리거용)
            # allow_new_service=True인 경우에만 즉시 전송 (정상 완료 시)
            # allow_new_service=False인 경우는 2초 후 별도 스레드에서 전송
            if allow_new_service:
                try:
                    send_wakeword_waiting_ready()
                except Exception as e:
                    # 로그 최소화: 전송 실패는 무시 가능하므로 로그 제거
                    pass
        except Exception as e:
            logger.error(f"❌ Wakeword 대기 상태 복귀 중 오류: {e}")
    
    try:
        while True:
            try:
                # ① 대기 상태 (마이크 ON, Wakeword 감지 중)
                # 서비스 진행 중이 아닐 때만 wakeword 감지기 활성화
                if not service_in_progress["in_progress"]:
                    # Wakeword 감지기가 활성화되어 있는지 확인 (루프 시작 시 항상 확인)
                    if wakeword_detector and wakeword_detector.interpreter is not None:
                        if wakeword_detector.is_paused:
                            wakeword_detector.resume()
                            mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
                
                # ② Wakeword 감지 대기 (타임아웃을 설정하여 주기적으로 상태 확인)
                # 서비스 진행 중이 아닐 때만 wakeword 감지 대기
                if service_in_progress["in_progress"]:
                    # 서비스 진행 중이면 wakeword 감지 대기하지 않고 계속 루프
                    time.sleep(0.5)
                    continue
                
                try:
                    # 1초 타임아웃으로 반복 호출하여 wakeword_start_waiting 이벤트에 반응 가능하도록 함
                    wakeword_detected = False
                    while not wakeword_detected and not service_in_progress["in_progress"]:
                        wakeword_detected = wait_for_wakeword(timeout=1.0)
                        if not wakeword_detected:
                            # 타임아웃 발생 (1초마다 반복)
                            # 서비스 진행 중이 아니고 wakeword 감지기가 활성화되어 있는지 확인
                            if not service_in_progress["in_progress"]:
                                if wakeword_detector and wakeword_detector.interpreter is not None:
                                    if wakeword_detector.is_paused:
                                        # 감지기가 일시 중지된 경우 재개
                                        wakeword_detector.resume()
                                        mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
                            # 계속 대기
                            continue
                    
                    # 서비스 진행 중이면 wakeword 감지 무시
                    if service_in_progress["in_progress"]:
                        continue
                    
                    # Wakeword 감지 로그
                    logger.info("🎤 Wakeword 감지됨")
                    
                    # 서비스 진행 중 플래그 설정
                    service_in_progress["in_progress"] = True
                    
                    # Wakeword 감지 후 즉시 wakeword 콜백 비활성화 (STT 세션 중 wakeword 감지 중지)
                    mic.disable_wakeword_callback()
                    if wakeword_detector:
                        wakeword_detector.pause()
                except Exception as e:
                    # Wakeword 감지 오류 시 예외 처리이므로 allow_new_service=False
                    reset_to_wakeword_waiting(f"Wakeword 감지 오류: {e}", allow_new_service=False)
                    continue
                
                # Wakeword 감지 이벤트를 브리지 서버로 전송 (Python 3.13 → FastAPI → 모바일)
                # FastAPI 연결 상태 확인 및 전송 시도
                wakeword_sent_successfully = False
                max_retry_attempts = 3
                retry_delay = 2  # 재시도 간격 (초)
                
                try:
                    for attempt in range(max_retry_attempts):
                        try:
                            result = send_wakeword_detected()
                            
                            if result:
                                wakeword_sent_successfully = True
                                break
                            else:
                                # 브리지 클라이언트가 연결되지 않음
                                if attempt < max_retry_attempts - 1:
                                    time.sleep(retry_delay)
                        except Exception as e:
                            if attempt < max_retry_attempts - 1:
                                time.sleep(retry_delay)
                except Exception as e:
                    # Wakeword 이벤트 전송 오류 시 예외 처리이므로 allow_new_service=False
                    reset_to_wakeword_waiting(f"Wakeword 이벤트 전송 오류: {e}", allow_new_service=False)
                    continue
                
                # FastAPI 연결 실패 시 wakeword 대기 상태로 복귀 (소켓 연결 오류)
                # 예외 처리이므로 allow_new_service=False로 호출하여 서비스 겹침 방지
                if not wakeword_sent_successfully:
                    reset_to_wakeword_waiting("Wakeword 이벤트 전송 실패", allow_new_service=False)
                    continue
                
                # 모바일에서 음성 파일 재생 완료 대기
                wakeword_audio_completed_flag = {"completed": False}
                
                def on_wakeword_audio_completed():
                    """모바일 음성 파일 재생 완료 콜백 (브리지 서버를 통해 호출됨)"""
                    wakeword_audio_completed_flag["completed"] = True
                
                # 모바일 음성 파일 재생 완료 콜백 등록
                set_wakeword_audio_completed_callback(on_wakeword_audio_completed)
                
                max_wait_time = 30  # 최대 30초 대기 (음성 파일 재생 시간)
                wait_start = time.time()
                
                while not wakeword_audio_completed_flag["completed"] and (time.time() - wait_start) < max_wait_time:
                    time.sleep(0.5)  # 0.5초마다 확인
                
                if not wakeword_audio_completed_flag["completed"]:
                    # 타임아웃 발생 시 예외 처리이므로 allow_new_service=False
                    reset_to_wakeword_waiting("모바일 음성 파일 재생 완료 신호 미수신 (타임아웃)", allow_new_service=False)
                    continue
                
                # ③~⑦ STT 세션 실행 (모드에 따라 버퍼링/스트리밍)
                try:
                    loop.run_until_complete(stt_session())
                except ValueError as e:
                    # 버퍼링 STT에서 음성이 감지되지 않은 경우 (None, 빈 텍스트, 타임아웃)
                    # 예외 처리이므로 allow_new_service=False
                    error_msg = str(e)
                    if "STT 결과가 None" in error_msg or "음성이 인식되지 않았습니다" in error_msg or "음성 입력 타임아웃" in error_msg:
                        reset_to_wakeword_waiting(f"음성 인식 실패: {error_msg}", allow_new_service=False)
                    else:
                        reset_to_wakeword_waiting(f"STT 세션 실행 오류: {e}", allow_new_service=False)
                    continue
                except Exception as e:
                    # 소켓 연결 오류 등 기타 예외
                    # 예외 처리이므로 allow_new_service=False
                    error_msg = str(e)
                    if "연결" in error_msg or "connection" in error_msg.lower() or "socket" in error_msg.lower():
                        reset_to_wakeword_waiting(f"소켓 연결 오류: {error_msg}", allow_new_service=False)
                    else:
                        reset_to_wakeword_waiting(f"STT 세션 실행 오류: {e}", allow_new_service=False)
                    continue
                
                # 서비스 완료 대기
                # - Operator 분기: 통신 종료 시 handle_mic_acquire()에서 플래그 설정
                # - CV 탐지 실패/정상: 통신 종료 시 handle_mic_acquire()에서 플래그 설정
                # - CV 탐지 성공: wakeword_start_waiting 이벤트로 handle_wakeword_start_waiting()에서 플래그 설정
                service_completed_flag_global["completed"] = False  # 플래그 리셋
                service_completed_flag = service_completed_flag_global  # 전역 플래그 사용
                
                def on_service_completed():
                    """서비스 완료 콜백 (브리지 서버를 통해 호출됨)"""
                    service_completed_flag["completed"] = True
                
                # 서비스 완료 콜백 등록
                set_service_completed_callback(on_service_completed)
                
                # 첫 이벤트 타임아웃: 7초 (Intent 분류 후 첫 이벤트가 오지 않으면 타임아웃)
                first_event_timeout = 7  # 7초
                wait_start = time.time()
                
                while not service_completed_flag["completed"]:
                    elapsed = time.time() - wait_start
                    
                    # 첫 이벤트 타임아웃 확인 (7초 내에 첫 이벤트가 오지 않으면 타임아웃)
                    if elapsed >= first_event_timeout and not service_completed_flag["completed"]:
                        # 타임아웃 발생 시 예외 처리이므로 allow_new_service=False
                        reset_to_wakeword_waiting(f"첫 이벤트 미수신 (타임아웃: {first_event_timeout}초)", allow_new_service=False)
                        break  # while 루프 종료하여 continue로 이동
                    
                    time.sleep(0.5)  # 0.5초마다 확인
                
                # 첫 이벤트 타임아웃이 발생한 경우 메인 루프의 다음 반복으로 이동
                if not service_completed_flag["completed"]:
                    continue
                
                # 서비스 완료 후 wakeword 감지 대기 상태로 복귀 (항상 실행)
                # 정상 완료이므로 allow_new_service=True로 호출하여 새로운 wakeword 감지 허용
                reset_to_wakeword_waiting("서비스 완료", allow_new_service=True)
                
                time.sleep(0.5)  # 0.5초 대기 (다음 루프 전)
            except Exception as e:
                # 메인 루프 실행 오류 시 예외 처리이므로 allow_new_service=False
                reset_to_wakeword_waiting(f"메인 루프 실행 오류: {e}", allow_new_service=False)
                time.sleep(1)  # 오류 후 잠시 대기
                # 예외 발생 후 다시 루프로 복귀
                continue
            except BaseException as e:
                # KeyboardInterrupt 등 시스템 예외도 처리
                if isinstance(e, KeyboardInterrupt):
                    raise  # KeyboardInterrupt는 상위로 전파
                # 시스템 예외 발생 시 예외 처리이므로 allow_new_service=False
                reset_to_wakeword_waiting(f"메인 루프 시스템 오류: {e}", allow_new_service=False)
                time.sleep(1)  # 오류 후 잠시 대기
                continue
    except KeyboardInterrupt:
        logger.info("🛑 종료 중...")
        streaming_stt.stop()
        mic.stop()
        stop_wakeword_detector()
        logger.info("✅ 종료 완료")
    except Exception as e:
        # 최상위 예외 처리 (예상치 못한 예외 - 루프 밖에서 발생)
        logger.error(f"❌ 최상위 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        try:
            # 최상위 예외 발생 시 예외 처리이므로 allow_new_service=False
            reset_to_wakeword_waiting(f"최상위 예외: {e}", allow_new_service=False)
            logger.warning("⚠️ 최상위 예외로 인해 루프가 중단되었습니다. 프로그램을 재시작하세요.")
        except Exception as recovery_error:
            logger.error(f"❌ 복구 시도 중 오류: {recovery_error}")
        # 최상위 예외는 복구 불가능하므로 프로그램 종료
        raise

if __name__ == "__main__":
    """
    라즈베리파이 메인 프로그램 (Python 3.10용)
    - Wakeword 감지 (Python 3.10에서만 동작)
    - 버퍼링/스트리밍 STT 실행 (Python 3.10에서만 동작)
    - STT 결과를 브리지 서버로 전송
    """
    run_stt_loop()

