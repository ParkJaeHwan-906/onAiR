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
    set_wakeword_audio_completed_callback,
    set_wakeword_start_waiting_callback, set_mic_off_callback, set_mic_on_callback,
    set_mic_release_callback, set_mic_acquire_callback
)
from server.app import manager  # ConnectionManager 인스턴스
from config import settings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 자동 모드 플래그 (전역 변수)
auto_mode_enabled = False

# ========================================
# 🐛 단계별 수동 실행 모드 (디버깅용) - 동기 버전
# ========================================

def wait_for_next_step_sync(step_name: str, step_number: str = ""):
    """
    단계별 수동 실행 모드: 다음 단계로 진행하기 전 대기 (동기 버전)
    
    Args:
        step_name: 현재 단계 이름 (로그 출력용)
        step_number: 단계 번호 (예: "1", "2", "3-1")
    
    사용법:
        - DEBUG_STEP_BY_STEP=True일 때: Enter 키 입력 대기
        - DEBUG_STEP_BY_STEP=False일 때: 바로 진행 (0.5초 딜레이만)
    """
    if not settings.DEBUG_STEP_BY_STEP:
        # 자동 모드: 짧은 딜레이만
        time.sleep(0.5)
        return
    
    # 자동 모드가 활성화되었으면 바로 진행
    global auto_mode_enabled
    if auto_mode_enabled:
        time.sleep(0.2)
        return
    
    # 수동 모드: 키보드 입력(Enter) 대기
    logger.info("=" * 80)
    logger.info(f"⏸️  [단계 {step_number}] {step_name} 완료")
    logger.info(f"   다음 단계로 진행하려면 Enter 키를 누르세요")
    logger.info(f"   (또는 자동 모드를 원하면 'auto'를 입력하고 Enter)")
    logger.info("=" * 80)
    
    try:
        user_input = input("   👆 Enter 키를 눌러 다음 단계 진행... ")
        if user_input.strip().lower() == "auto":
            logger.info(f"✅ 자동 모드 활성화 - 이후 단계는 자동 진행됩니다")
            auto_mode_enabled = True
        else:
            logger.info(f"✅ 다음 단계 진행: {step_name}")
    except (EOFError, KeyboardInterrupt):
        # 입력이 불가능한 환경(백그라운드 실행 등)에서는 자동 진행
        logger.info(f"⚠️ 키보드 입력을 받을 수 없습니다. 자동으로 다음 단계 진행")
    except Exception as e:
        logger.warning(f"⚠️ 입력 처리 오류: {e}, 자동으로 다음 단계 진행")
    
    logger.info("=" * 80)


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
    bridge_thread = threading.Thread(
        target=run_server,
        args=('127.0.0.1', 5050),
        daemon=True
    )
    bridge_thread.start()
    logger.info("🚀 STT 브리지 서버 시작 (포트 5050)")
    logger.info("   Python 3.13에서 브리지 클라이언트가 연결할 수 있습니다.")
    
    # 브리지 서버가 시작될 때까지 잠시 대기
    time.sleep(1)
    
    # WebRTC 프로세스 확인 및 오디오 스트리밍 상태 확인
    logger.info("🔍 WebRTC 프로세스 및 오디오 스트리밍 상태 확인 중...")
    
    # WebRTC 프로세스(socket_manager.py) 실행 중인지 확인
    # 주의: WebRTC 프로세스는 OPERATOR Intent나 통신 요청 시에만 오디오 스트리밍을 시작함
    # 평소에는 실행 중이어도 마이크를 점유하지 않아야 함
    webrtc_pids = []
    try:
        result = subprocess.run(['pgrep', '-f', 'socket_manager.py'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            webrtc_pids = [pid for pid in pids if pid]
            if webrtc_pids:
                logger.info(f"ℹ️ WebRTC 프로세스(socket_manager.py)가 실행 중입니다 (PID: {', '.join(webrtc_pids)})")
                logger.info("   평소에는 마이크를 점유하지 않아야 합니다.")
                
                # WebRTC 프로세스가 마이크를 점유하고 있는지 확인
                # lsof를 사용하여 /dev/snd 디바이스를 사용 중인 프로세스 확인
                try:
                    lsof_result = subprocess.run(['lsof', '/dev/snd/*'], capture_output=True, text=True, timeout=2)
                    if lsof_result.returncode == 0 and lsof_result.stdout:
                        # WebRTC 프로세스 PID가 lsof 결과에 있는지 확인
                        for pid in webrtc_pids:
                            if pid in lsof_result.stdout:
                                logger.warning("=" * 60)
                                logger.warning(f"⚠️ WebRTC 프로세스(PID: {pid})가 마이크를 점유하고 있습니다!")
                                logger.warning("   FastAPI 서버에서 'handle_audio_stream' (start: False) 이벤트를 전송하여")
                                logger.warning("   WebRTC 오디오 스트리밍을 중지해야 합니다.")
                                logger.warning("=" * 60)
                                logger.warning("   임시 해결 방법: WebRTC 프로세스 재시작")
                                logger.warning(f"   $ pkill -f socket_manager.py")
                                logger.warning("=" * 60)
                except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                    logger.debug(f"lsof 확인 실패 (무시 가능): {e}")
                
                time.sleep(0.5)  # 잠시 대기
    except Exception as e:
        logger.warning(f"⚠️ WebRTC 프로세스 확인 실패: {e}")
    
    # 주의: 마이크 점유 확인은 MicStream.start()에서 직접 수행됩니다.
    # MicStream.start()는 자동으로 장치를 선택하고 마이크를 열며,
    # WebRTC 프로세스가 마이크를 점유하고 있으면 적절한 오류 메시지를 출력합니다.
    
    # 마이크 초기화 및 시작 (항상 켜져있음)
    mic = MicStream()
    
    # Wakeword 감지기 초기화 (마이크 시작 전에 초기화)
    wakeword_detector = init_wakeword_detector()
    
    # MicStream에 Wakeword 감지기 콜백 연결
    if wakeword_detector and wakeword_detector.interpreter is not None:
        mic.set_wakeword_callback(wakeword_detector.process_audio_chunk)
        logger.info("✅ Wakeword 감지기가 MicStream에 연결되었습니다")
    
    # 마이크 시작 (마이크 점유 확인 및 오류 처리 포함)
    # 주의: WebRTC 프로세스는 평소에 마이크를 점유하지 않으므로,
    # 마이크를 열 때 문제가 발생하면 MicStream.start()에서 적절한 오류 메시지가 출력됩니다.
    try:
        mic.start()  # 스트림 생성 및 시작 (마이크 ON)
        logger.info("🔊 마이크 ON (항상 활성 상태)")
    except Exception as e:
        logger.error("❌ 마이크 시작 실패")
        logger.error("   해결 방법:")
        logger.error("   1. WebRTC 오디오 스트리밍이 실행 중인지 확인:")
        logger.error("      FastAPI 서버에서 'handle_audio_stream' (start: False) 이벤트 전송")
        logger.error("   2. 다른 프로세스가 마이크를 사용 중인지 확인: $ lsof | grep -i audio")
        logger.error("   3. ALSA 레벨에서 마이크 확인: $ arecord -l")
        logger.error("   4. WebRTC 프로세스 중지 (최후의 수단): $ pkill -f socket_manager.py")
        raise RuntimeError("마이크를 사용할 수 없습니다. WebRTC 오디오 스트리밍이나 다른 프로세스가 마이크를 점유하고 있을 수 있습니다.") from e
    
    # STT 인스턴스 생성
    buffered_stt = GcpBufferedStt()
    streaming_stt = GcpStreamingStt()
    
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
                await buffered_stt.run(mic, broadcast)
                # 버퍼링 STT 후 텍스트 전송 완료 → 마이크는 buffered_stt.run() 내부에서 OFF됨
            else:
                # 스트리밍 방식: 실시간 인식 (분기처리 이후)
                logger.info("🎤 스트리밍 모드 시작 (실시간 음성 인식)")
                # 마이크 다시 활성화 (Intent 분류 중간에 OFF되었을 수 있음)
                if not mic.is_active():
                    mic.resume()
                    logger.info("🔊 마이크 ON (스트리밍 모드 시작)")
                
                # 세션 ID 생성 (Clarify 세션용)
                import uuid
                session_id = str(uuid.uuid4())
                
                logger.info(f"📤 브리지 서버를 통해 Streaming STT 전송 시작 (session_id={session_id})")
                await streaming_stt.run(mic, broadcaster=broadcast, session_id=session_id)
                # 스트리밍 종료 후 마이크는 켜둠 (다음 Wakeword 대기)
                logger.info("🟢 스트리밍 모드 종료, 마이크는 계속 ON")
                
        except Exception as e:
            logger.error(f"❌ STT 세션 오류: {e}")
            # 에러 발생 시에도 마이크는 켜둠 (다음 Wakeword 대기를 위해)
            if not mic.is_active():
                mic.resume()
    
    # 이벤트 루프 생성
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Streaming STT 시작 함수 (Python 3.13에서 호출될 수 있음)
    # 주의: loop가 정의된 후에 등록해야 함
    def start_streaming_stt(session_id: str):
        """브리지 서버를 통해 받은 Streaming STT 시작 명령 처리"""
        logger.info("=" * 60)
        logger.info(f"📥 [단계 12-3] Python 3.10: Streaming STT 시작 명령 수신")
        logger.info(f"   Session ID: {session_id}")
        logger.info("=" * 60)
        wait_for_next_step_sync("Streaming STT 시작 명령 수신", "12-3")
        
        # 마이크 활성화 (버퍼링 STT 후 OFF되었을 수 있음)
        if not mic.is_active():
            logger.info("=" * 60)
            logger.info("🔊 [단계 12-4] 마이크 활성화 시작")
            logger.info("=" * 60)
            mic.resume()
            logger.info("✅ [단계 12-4 완료] 마이크 ON (Streaming STT 시작)")
            wait_for_next_step_sync("마이크 활성화 완료", "12-4")
        else:
            logger.info("ℹ️ 마이크가 이미 활성화되어 있습니다.")
        
        # Streaming STT 세션 시작 (별도 태스크로 실행)
        async def run_streaming():
            try:
                logger.info("=" * 60)
                logger.info(f"🎤 [단계 12-5] 실시간 Streaming STT 세션 시작")
                logger.info(f"   Session ID: {session_id}")
                logger.info("=" * 60)
                await streaming_stt.run(mic, broadcaster=broadcast, session_id=session_id)
                logger.info("=" * 60)
                logger.info("🟢 [단계 12-5 완료] Streaming STT 세션 종료")
                logger.info("=" * 60)
            except Exception as e:
                logger.error("=" * 60)
                logger.error(f"❌ [단계 12-5 실패] Streaming STT 세션 오류: {e}")
                logger.error("=" * 60)
        
        # 이벤트 루프에서 실행
        loop.call_soon_threadsafe(lambda: asyncio.create_task(run_streaming()))
    
    # 브리지 서버에 Streaming STT 시작 콜백 등록
    set_start_streaming_stt_callback(start_streaming_stt)
    
    # Wakeword 감지 대기 시작 콜백 등록
    def handle_wakeword_start_waiting():
        """Wakeword 감지 대기 시작 처리"""
        logger.info("=" * 60)
        logger.info("🔊 Wakeword 감지 대기 시작")
        logger.info("=" * 60)
        if wakeword_detector and wakeword_detector.interpreter is not None:
            wakeword_detector.resume()
            mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
            logger.info("✅ Wakeword 감지기 재활성화 완료")
        else:
            logger.warning("⚠️ Wakeword 감지기가 초기화되지 않았습니다")
    
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
        mic.release()  # 마이크 스트림을 완전히 닫아서 장치를 해제
    
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
    
    set_mic_acquire_callback(handle_mic_acquire)
    
    logger.info("🎧 STT 루프 대기 시작 (마이크 ON, Wakeword 감지 중)")
    logger.info("📌 Python 3.10에서 실행 중 (wakeword + STT)")
    
    try:
        while True:
            # ① 대기 상태 (마이크 ON, Wakeword 감지 중)
            logger.info("=" * 60)
            logger.info("⏳ [단계 1] Wakeword 감지 대기 중...")
            logger.info("=" * 60)
            
            # ② Wakeword 감지 대기
            if wait_for_wakeword():
                logger.info("=" * 60)
                logger.info("✅ [단계 2] Wakeword 감지 완료!")
                logger.info("=" * 60)
                wait_for_next_step_sync("Wakeword 감지 완료", "2")
                time.sleep(0.5)  # 0.5초 대기 (단계 구분)
                
                # Wakeword 감지 후 즉시 wakeword 콜백 비활성화 (STT 세션 중 wakeword 감지 중지)
                logger.info("🔇 Wakeword 감지기 일시 중지 (STT 세션 중)")
                mic.disable_wakeword_callback()
                # Wakeword 감지기 자체도 일시 중지
                if wakeword_detector:
                    wakeword_detector.pause()
                
                # Wakeword 감지 이벤트를 브리지 서버로 전송 (Python 3.13 → FastAPI → 모바일)
                logger.info("=" * 60)
                logger.info("📤 [단계 2-1] 브리지 서버로 Wakeword 감지 이벤트 전송")
                logger.info("=" * 60)
                send_wakeword_detected()
                wait_for_next_step_sync("Wakeword 감지 이벤트 전송 완료", "2-1")
                
                # 모바일에서 음성 파일 재생 완료 대기
                logger.info("=" * 60)
                logger.info("⏳ [단계 2-2] 모바일 음성 파일 재생 완료 대기 중...")
                logger.info("   💡 모바일에서 'onAir 서비스를 시작합니다. 어떤 것을 도와드릴까요?' 재생 중...")
                logger.info("=" * 60)
                
                wakeword_audio_completed_flag = {"completed": False}  # 딕셔너리로 래핑하여 참조 전달
                
                def on_wakeword_audio_completed():
                    """모바일 음성 파일 재생 완료 콜백 (브리지 서버를 통해 호출됨)"""
                    wakeword_audio_completed_flag["completed"] = True
                    logger.info("=" * 60)
                    logger.info("✅ 모바일 음성 파일 재생 완료 신호 수신")
                    logger.info("=" * 60)
                    # 디버그 모드에서 Enter 키 대기 (콜백 내부에서 호출)
                    wait_for_next_step_sync("모바일 음성 파일 재생 완료", "2-2")
                
                # 모바일 음성 파일 재생 완료 콜백 등록
                set_wakeword_audio_completed_callback(on_wakeword_audio_completed)
                
                max_wait_time = 30  # 최대 30초 대기 (음성 파일 재생 시간)
                wait_start = time.time()
                
                while not wakeword_audio_completed_flag["completed"] and (time.time() - wait_start) < max_wait_time:
                    time.sleep(0.5)  # 0.5초마다 확인
                
                if not wakeword_audio_completed_flag["completed"]:
                    logger.warning("=" * 60)
                    logger.warning("⚠️ 모바일 음성 파일 재생 완료 신호를 받지 못했습니다. 타임아웃으로 버퍼링 STT 시작")
                    logger.warning("=" * 60)
                    # 타임아웃 시에도 디버그 모드에서 Enter 키 대기
                    wait_for_next_step_sync("모바일 음성 파일 재생 완료 (타임아웃)", "2-2")
                else:
                    logger.info("=" * 60)
                    logger.info("✅ [단계 2-2 완료] 모바일 음성 파일 재생 완료")
                    logger.info("=" * 60)
                    # 콜백 내부에서 이미 wait_for_next_step_sync 호출됨
                
                logger.info("=" * 60)
                logger.info("🎤 [단계 3] 버퍼링 STT 세션 시작")
                logger.info("=" * 60)
                wait_for_next_step_sync("버퍼링 STT 세션 시작", "3")
                
                # ③~⑦ STT 세션 실행 (모드에 따라 버퍼링/스트리밍)
                loop.run_until_complete(stt_session())
                
                logger.info("=" * 60)
                logger.info("🟢 [단계 완료] STT 세션 종료, 서비스 완료 대기 중...")
                logger.info("=" * 60)
                wait_for_next_step_sync("STT 세션 종료", "완료")
                
                # 서비스 완료 대기 (FastAPI 서버에서 GPT-4o 답변 생성 및 TTS 완료 후 service_completed 이벤트 수신)
                # 주의: Python 3.10과 Python 3.13은 별도 프로세스이므로 메모리를 공유할 수 없음
                # 따라서 브리지 서버를 통해 서비스 완료 신호를 받아야 함
                logger.info("⏳ 서비스 완료 대기 중... (GPT-4o 답변 생성 및 TTS 완료 후 wakeword 재활성화)")
                service_completed_flag = {"completed": False}  # 딕셔너리로 래핑하여 참조 전달
                
                def on_service_completed():
                    """서비스 완료 콜백 (브리지 서버를 통해 호출됨)"""
                    service_completed_flag["completed"] = True
                    logger.info("=" * 60)
                    logger.info("✅ 서비스 완료 신호 수신: GPT-4o 답변 생성 및 TTS 완료")
                    logger.info("=" * 60)
                
                # 서비스 완료 콜백 등록
                set_service_completed_callback(on_service_completed)
                
                max_wait_time = 300  # 최대 5분 대기
                wait_start = time.time()
                
                while not service_completed_flag["completed"] and (time.time() - wait_start) < max_wait_time:
                    time.sleep(0.5)  # 0.5초마다 확인
                
                if not service_completed_flag["completed"]:
                    logger.warning("=" * 60)
                    logger.warning("⚠️ 서비스 완료 신호를 받지 못했습니다. 타임아웃으로 wakeword 재활성화")
                    logger.warning("=" * 60)
                
                # 서비스 완료 후 wakeword 콜백 재활성화 (옵션)
                if settings.REENABLE_WAKEWORD_AFTER_SERVICE:
                    if wakeword_detector and wakeword_detector.interpreter is not None:
                        logger.info("🔊 Wakeword 감지기 재활성화 (다음 wakeword 대기)")
                        wakeword_detector.resume()  # Wakeword 감지기 재개
                        mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
                        # 서비스 완료 플래그 리셋
                        service_completed_flag["completed"] = False
                else:
                    logger.info("⏸️ 설정에 따라 wakeword 감지기 재활성화를 건너뜁니다 (REENABLE_WAKEWORD_AFTER_SERVICE=False)")
                
                time.sleep(0.5)  # 0.5초 대기 (다음 루프 전)
    except KeyboardInterrupt:
        logger.info("🛑 종료 중...")
        streaming_stt.stop()
        mic.stop()
        stop_wakeword_detector()
        logger.info("✅ 종료 완료")

if __name__ == "__main__":
    """
    라즈베리파이 메인 프로그램 (Python 3.10용)
    - Wakeword 감지 (Python 3.10에서만 동작)
    - 버퍼링/스트리밍 STT 실행 (Python 3.10에서만 동작)
    - STT 결과를 브리지 서버로 전송
    """
    run_stt_loop()

