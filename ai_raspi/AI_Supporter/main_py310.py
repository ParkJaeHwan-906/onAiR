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
    # 브리지 서버를 별도 스레드에서 실행
    bridge_thread = None
    try:
        bridge_thread = threading.Thread(
            target=run_server,
            args=('127.0.0.1', 5050),
            daemon=True
        )
        bridge_thread.start()
        logger.info("🚀 브리지 서버 시작 (포트 5050)")
        
        # 브리지 서버가 시작될 때까지 잠시 대기
        time.sleep(1)
        
        # 포트가 실제로 열렸는지 확인
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 5050))
        sock.close()
        if result != 0:
            logger.warning("⚠️ 브리지 서버 포트 연결 확인 실패. 서버가 시작되지 않았을 수 있습니다.")
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ 브리지 서버 시작 실패: {e}")
        logger.error("   해결 방법:")
        logger.error("   1. 포트 5050을 사용 중인 프로세스 확인: sudo lsof -i :5050")
        logger.error("   2. 프로세스 종료: sudo kill -9 <PID>")
        logger.error("   3. 또는 모든 main_py310.py 프로세스 종료: pkill -f main_py310.py")
        logger.error("=" * 60)
        raise RuntimeError(f"브리지 서버를 시작할 수 없습니다: {e}") from e
    
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
    
    # 마이크 초기화 및 시작
    mic = MicStream()
    wakeword_detector = init_wakeword_detector()
    
    if wakeword_detector and wakeword_detector.interpreter is not None:
        mic.set_wakeword_callback(wakeword_detector.process_audio_chunk)
    
    try:
        mic.start()
        logger.info("🔊 마이크 ON")
    except Exception as e:
        logger.error(f"❌ 마이크 시작 실패: {e}")
        raise RuntimeError("마이크를 사용할 수 없습니다.") from e
    
    # STT 인스턴스 생성
    buffered_stt = GcpBufferedStt()
    streaming_stt = GcpStreamingStt()
    
    # 버퍼링 STT 실행 중 플래그 (중지 가능하도록)
    buffered_stt_running = {"running": False}
    
    async def broadcast(msg):
        """STT 결과를 브리지 서버(Socket.IO)로 전송"""
        send_stt_result(msg)
    
    async def stt_session():
        """STT 세션 실행 (모드에 따라 버퍼링/스트리밍 선택)"""
        try:
            # 모드 확인 (기본값: buffered)
            mode = "buffered"  # Python 3.13에서 모드 전환 명령을 받을 수 있도록 확장 가능
            
            if mode == "buffered":
                # 버퍼링 방식: 3~5초 수집 후 일괄 처리 (분기처리 이전)
                # 마이크는 이미 켜져있음
                buffered_stt_running["running"] = True
                try:
                    await buffered_stt.run(mic, broadcast)
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
        logger.info(f"🛑 버퍼링 STT 세션 종료 신호 수신: {reason}")
    
    set_stop_buffered_stt_callback(handle_stop_buffered_stt)
    
    # Wakeword 감지 대기 시작 콜백 등록
    def handle_wakeword_start_waiting():
        """Wakeword 감지 대기 시작 처리"""
        if wakeword_detector and wakeword_detector.interpreter is not None:
            wakeword_detector.resume()
            mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
            logger.info("✅ Wakeword 감지 대기 시작")
            
            # FastAPI로 Wakeword 대기 준비 완료 이벤트 전송 (YOLO 서버 API 요청 트리거용)
            try:
                send_wakeword_waiting_ready()
                logger.info("📤 FastAPI로 Wakeword 대기 준비 완료 이벤트 전송 완료")
            except Exception as e:
                logger.warning(f"⚠️ Wakeword 대기 준비 이벤트 전송 실패 (무시 가능): {e}")
    
    set_wakeword_start_waiting_callback(handle_wakeword_start_waiting)
    
    # STT 목적 음성 수집 중지 콜백 등록
    def handle_mic_off():
        """STT 목적 음성 수집 중지 처리"""
        logger.info("=" * 60)
        logger.info("🔇 STT 목적 음성 수집 중지")
        logger.info("   주의: 마이크는 하나이며, STT 목적으로 사용 중이던 스트림을 중지합니다.")
        logger.info("=" * 60)
        mic.pause()
    
    set_mic_off_callback(handle_mic_off)
    
    # STT 목적 음성 수집 재개 콜백 등록
    def handle_mic_on():
        """STT 목적 음성 수집 재개 처리"""
        logger.info("=" * 60)
        logger.info("🔊 STT 목적 음성 수집 재개")
        logger.info("   주의: 마이크는 하나이며, STT 목적으로 음성을 수집합니다.")
        logger.info("=" * 60)
        if not mic.is_active():
            mic.resume()
        else:
            logger.info("ℹ️ STT 목적 음성 수집이 이미 활성화되어 있습니다")
    
    set_mic_on_callback(handle_mic_on)
    
    # 마이크 장치 해제 콜백 등록 (WebRTC 프로세스가 마이크를 사용할 수 있도록)
    def handle_mic_release():
        """마이크 장치 해제 처리 (WebRTC 프로세스가 마이크를 사용할 수 있도록)"""
        logger.info("=" * 60)
        logger.info("🔇 마이크 장치 해제 (WebRTC 프로세스가 사용할 수 있음)")
        logger.info("   주의: 마이크는 하나이며, WebRTC 프로세스가 마이크를 점유합니다.")
        logger.info("=" * 60)
        
        # Wakeword 감지기 일시 중지 (마이크 해제 중에는 wakeword 감지 불가)
        if wakeword_detector and wakeword_detector.interpreter is not None:
            logger.info("🔇 Wakeword 감지기 일시 중지 (마이크 해제 중)")
            wakeword_detector.pause()
            mic.disable_wakeword_callback()  # Wakeword 콜백 비활성화
            logger.info("✅ Wakeword 감지기 일시 중지 완료")
        
        mic.release()  # 마이크 스트림을 완전히 닫아서 장치를 해제
        logger.info("✅ 마이크 장치 해제 완료 (WebRTC 프로세스가 마이크를 사용할 수 있음)")
    
    set_mic_release_callback(handle_mic_release)
    
    # 마이크 장치 재점유 콜백 등록 (WebRTC 프로세스가 마이크를 해제한 후)
    def handle_mic_acquire():
        """마이크 장치 재점유 처리 (WebRTC 프로세스가 마이크를 해제한 후)"""
        logger.info("=" * 60)
        logger.info("🔊 마이크 장치 재점유 (WebRTC 프로세스가 마이크를 해제한 후)")
        logger.info("   주의: 마이크는 하나이며, Python 3.10 프로세스가 마이크를 점유합니다.")
        logger.info("=" * 60)
        mic.acquire()  # 마이크 스트림을 다시 시작해서 장치를 재점유
        # 재점유 후 논리적으로도 ON 상태로 설정
        if mic.is_paused:
            mic.resume()
        
        # 마이크 재점유 후 Wakeword 감지 대기 상태로 복귀
        # 주의: communication_close 이벤트 후 wakeword_start_waiting 이벤트도 별도로 전송되지만,
        # 여기서도 재활성화하여 안전하게 처리
        if wakeword_detector and wakeword_detector.interpreter is not None:
            logger.info("=" * 60)
            logger.info("🔊 Wakeword 감지기 재활성화 (통신 종료 후 대기 상태 복귀)")
            logger.info("=" * 60)
            wakeword_detector.resume()  # Wakeword 감지기 재개
            mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
            logger.info("✅ Wakeword 감지 대기 상태로 복귀 완료")
        else:
            logger.warning("⚠️ Wakeword 감지기가 초기화되지 않았습니다")
        
        # 버퍼링 STT 실행 상태 리셋 (혹시 실행 중이었다면)
        buffered_stt_running["running"] = False
        logger.info("✅ 마이크 재점유 및 Wakeword 감지 대기 상태 복귀 완료")
        
        # FastAPI로 Wakeword 대기 준비 완료 이벤트 전송 (YOLO 서버 API 요청 트리거용)
        try:
            send_wakeword_waiting_ready()
            logger.info("📤 FastAPI로 Wakeword 대기 준비 완료 이벤트 전송 완료")
        except Exception as e:
            logger.warning(f"⚠️ Wakeword 대기 준비 이벤트 전송 실패 (무시 가능): {e}")
    
    set_mic_acquire_callback(handle_mic_acquire)
    
    logger.info("🎧 STT 루프 시작 (Wakeword 감지 대기 중)")
    
    def reset_to_wakeword_waiting(reason: str = "알 수 없는 오류"):
        """
        Wakeword 감지 대기 상태로 복귀
        
        Args:
            reason: 복귀 이유
        """
        logger.warning("=" * 60)
        logger.warning(f"⚠️ Wakeword 감지 대기 상태로 복귀: {reason}")
        logger.warning("=" * 60)
        
        try:
            # 마이크 상태 확인 및 활성화
            if not mic.is_active():
                mic.resume()
            
            # Wakeword 감지기 재개
            if wakeword_detector and wakeword_detector.interpreter is not None:
                wakeword_detector.resume()
                mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
                logger.info("✅ Wakeword 감지기 재개 완료")
            
            # 버퍼링 STT 실행 상태 리셋
            buffered_stt_running["running"] = False
            
            logger.info("✅ Wakeword 감지 대기 상태로 복귀 완료")
            
            # FastAPI로 Wakeword 대기 준비 완료 이벤트 전송 (YOLO 서버 API 요청 트리거용)
            try:
                send_wakeword_waiting_ready()
                logger.info("📤 FastAPI로 Wakeword 대기 준비 완료 이벤트 전송 완료")
            except Exception as e:
                logger.warning(f"⚠️ Wakeword 대기 준비 이벤트 전송 실패 (무시 가능): {e}")
        except Exception as e:
            logger.error(f"❌ Wakeword 대기 상태 복귀 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    try:
        while True:
            try:
                # ① 대기 상태 (마이크 ON, Wakeword 감지 중)
                logger.info("⏳ Wakeword 감지 대기 중...")
                
                # ② Wakeword 감지 대기
                try:
                    wakeword_detected = wait_for_wakeword()
                    if not wakeword_detected:
                        # Wakeword 감지 실패 (타임아웃 등)
                        logger.warning("⚠️ Wakeword 감지 실패 또는 타임아웃")
                        reset_to_wakeword_waiting("Wakeword 감지 실패")
                        continue
                    
                    logger.info("✅ Wakeword 감지 완료")
                    
                    # Wakeword 감지 후 즉시 wakeword 콜백 비활성화 (STT 세션 중 wakeword 감지 중지)
                    mic.disable_wakeword_callback()
                    if wakeword_detector:
                        wakeword_detector.pause()
                except Exception as e:
                    logger.error(f"❌ Wakeword 감지 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    reset_to_wakeword_waiting(f"Wakeword 감지 오류: {e}")
                    continue
                
                # Wakeword 감지 이벤트를 브리지 서버로 전송 (Python 3.13 → FastAPI → 모바일)
                logger.info("📤 Wakeword 감지 이벤트 전송")
                
                # FastAPI 연결 상태 확인 및 전송 시도
                wakeword_sent_successfully = False
                max_retry_attempts = 3
                retry_delay = 2  # 재시도 간격 (초)
                
                try:
                    for attempt in range(max_retry_attempts):
                        try:
                            # 브리지 클라이언트 연결 상태 확인 (Python 3.13 프로세스 확인)
                            # 주의: 브리지 서버는 Python 3.10에서 실행되므로 항상 연결 가능
                            # 하지만 브리지 클라이언트(Python 3.13)가 FastAPI에 연결되어 있는지 확인 필요
                            result = send_wakeword_detected()
                            
                            if result:
                                # 브리지 클라이언트로 전송 성공
                                wakeword_sent_successfully = True
                                logger.info("✅ Wakeword 감지 이벤트 전송 완료")
                                break
                            else:
                                # 브리지 클라이언트가 연결되지 않음 (Python 3.13 프로세스가 실행되지 않음)
                                if attempt < max_retry_attempts - 1:
                                    logger.warning(f"⚠️ 브리지 클라이언트 연결 실패, {retry_delay}초 후 재시도 ({attempt + 1}/{max_retry_attempts})")
                                    time.sleep(retry_delay)
                                else:
                                    logger.error("❌ 브리지 클라이언트 연결 실패 (최대 재시도 횟수 초과)")
                        except Exception as e:
                            if attempt < max_retry_attempts - 1:
                                logger.warning(f"⚠️ Wakeword 이벤트 전송 실패, {retry_delay}초 후 재시도 ({attempt + 1}/{max_retry_attempts}): {e}")
                                time.sleep(retry_delay)
                            else:
                                logger.error(f"❌ Wakeword 이벤트 전송 실패 (최대 재시도 횟수 초과): {e}")
                except Exception as e:
                    logger.error(f"❌ Wakeword 이벤트 전송 중 예외 발생: {e}")
                    import traceback
                    traceback.print_exc()
                    reset_to_wakeword_waiting(f"Wakeword 이벤트 전송 오류: {e}")
                    continue
                
                # FastAPI 연결 실패 시 wakeword 대기 상태로 복귀
                if not wakeword_sent_successfully:
                    logger.warning("⚠️ FastAPI 서버 연결 실패 - Wakeword 대기 상태로 복귀")
                    reset_to_wakeword_waiting("FastAPI 서버 연결 실패")
                    continue
                
                # 모바일에서 음성 파일 재생 완료 대기
                logger.info("⏳ 모바일 음성 파일 재생 완료 대기 중...")
                
                wakeword_audio_completed_flag = {"completed": False}  # 딕셔너리로 래핑하여 참조 전달
                
                def on_wakeword_audio_completed():
                    """모바일 음성 파일 재생 완료 콜백 (브리지 서버를 통해 호출됨)"""
                    wakeword_audio_completed_flag["completed"] = True
                    logger.info("✅ 모바일 음성 파일 재생 완료 신호 수신")
                
                # 모바일 음성 파일 재생 완료 콜백 등록
                set_wakeword_audio_completed_callback(on_wakeword_audio_completed)
                
                max_wait_time = 30  # 최대 30초 대기 (음성 파일 재생 시간)
                wait_start = time.time()
                
                while not wakeword_audio_completed_flag["completed"] and (time.time() - wait_start) < max_wait_time:
                    time.sleep(0.5)  # 0.5초마다 확인
                
                if not wakeword_audio_completed_flag["completed"]:
                    logger.warning("⚠️ 모바일 음성 파일 재생 완료 신호 미수신 - Wakeword 대기 상태로 복귀")
                    reset_to_wakeword_waiting("모바일 음성 파일 재생 완료 신호 미수신")
                    continue
                
                # 모바일 음성 파일 재생 완료 → 버퍼링 STT 세션 시작
                logger.info("🎤 버퍼링 STT 세션 시작")
                
                # ③~⑦ STT 세션 실행 (모드에 따라 버퍼링/스트리밍)
                try:
                    loop.run_until_complete(stt_session())
                    logger.info("✅ STT 세션 완료")
                except Exception as e:
                    logger.error(f"❌ STT 세션 실행 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    reset_to_wakeword_waiting(f"STT 세션 실행 오류: {e}")
                    continue
                
                # 서비스 완료 대기 (FastAPI 서버에서 GPT-4o 답변 생성 및 TTS 완료 후 service_completed 이벤트 수신)
                service_completed_flag = {"completed": False}
                
                def on_service_completed():
                    """서비스 완료 콜백 (브리지 서버를 통해 호출됨)"""
                    service_completed_flag["completed"] = True
                    logger.info("✅ 서비스 완료 신호 수신")
                
                # 서비스 완료 콜백 등록
                set_service_completed_callback(on_service_completed)
                
                max_wait_time = 300  # 최대 5분 대기
                wait_start = time.time()
                
                while not service_completed_flag["completed"] and (time.time() - wait_start) < max_wait_time:
                    time.sleep(0.5)  # 0.5초마다 확인
                
                if not service_completed_flag["completed"]:
                    logger.warning("⚠️ 서비스 완료 신호 미수신 (타임아웃) - Wakeword 대기 상태로 복귀")
                    reset_to_wakeword_waiting("서비스 완료 신호 미수신 (타임아웃)")
                    continue
                
                # 서비스 완료 후 wakeword 콜백 재활성화 (옵션)
                if settings.REENABLE_WAKEWORD_AFTER_SERVICE:
                    if wakeword_detector and wakeword_detector.interpreter is not None:
                        wakeword_detector.resume()
                        mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
                        service_completed_flag["completed"] = False
                
                time.sleep(0.5)  # 0.5초 대기 (다음 루프 전)
            except Exception as e:
                logger.error(f"❌ 메인 루프 실행 중 예외 발생: {e}")
                import traceback
                traceback.print_exc()
                reset_to_wakeword_waiting(f"메인 루프 실행 오류: {e}")
                time.sleep(1)  # 오류 후 잠시 대기
                # 예외 발생 후 다시 루프로 복귀
                continue
            except BaseException as e:
                # KeyboardInterrupt 등 시스템 예외도 처리
                if isinstance(e, KeyboardInterrupt):
                    raise  # KeyboardInterrupt는 상위로 전파
                logger.error(f"❌ 메인 루프 실행 중 시스템 예외 발생: {e}")
                import traceback
                traceback.print_exc()
                reset_to_wakeword_waiting(f"메인 루프 시스템 오류: {e}")
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
            reset_to_wakeword_waiting(f"최상위 예외: {e}")
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

