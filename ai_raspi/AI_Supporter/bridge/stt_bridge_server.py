import socketio
import logging

logger = logging.getLogger(__name__)

# 1️⃣ Socket.IO 서버 생성
sio = socketio.Server(cors_allowed_origins='*', async_mode='threading')
app = socketio.WSGIApp(sio)

# 연결된 클라이언트 세션 ID 저장
connected_clients = set()

# Streaming STT 시작 콜백 (Python 3.10에서 설정)
start_streaming_stt_callback = None

# 서비스 완료 콜백 (Python 3.10에서 설정)
service_completed_callback = None

# 모바일 음성 파일 재생 완료 콜백 (Python 3.10에서 설정)
wakeword_audio_completed_callback = None

def set_start_streaming_stt_callback(callback):
    """Streaming STT 시작 콜백 설정 (Python 3.10에서 호출)"""
    global start_streaming_stt_callback
    start_streaming_stt_callback = callback
    logger.info("✅ Streaming STT 시작 콜백이 등록되었습니다")

def set_service_completed_callback(callback):
    """서비스 완료 콜백 설정 (Python 3.10에서 호출)"""
    global service_completed_callback
    service_completed_callback = callback
    logger.info("✅ 서비스 완료 콜백이 등록되었습니다")

def set_wakeword_audio_completed_callback(callback):
    """모바일 음성 파일 재생 완료 콜백 설정 (Python 3.10에서 호출)"""
    global wakeword_audio_completed_callback
    wakeword_audio_completed_callback = callback
    logger.info("✅ 모바일 음성 파일 재생 완료 콜백이 등록되었습니다")

# 2️⃣ 클라이언트 연결 이벤트
@sio.event
def connect(sid, environ):
    connected_clients.add(sid)
    logger.info(f"✅ 브리지 클라이언트 연결됨: {sid} (총 {len(connected_clients)}개 연결)")

@sio.event
def disconnect(sid):
    connected_clients.discard(sid)
    logger.info(f"❌ 브리지 클라이언트 연결 종료: {sid} (남은 연결: {len(connected_clients)}개)")

# Streaming STT 시작 명령 수신 (Python 3.13 → Python 3.10)
@sio.on('start_streaming_stt')
def handle_start_streaming_stt(sid, data):
    """Python 3.13에서 Streaming STT 시작 명령 수신"""
    session_id = data.get("session_id")
    logger.info("=" * 60)
    logger.info(f"📥 [단계 12-2] 브리지 서버: Streaming STT 시작 명령 수신")
    logger.info(f"   Session ID: {session_id}")
    logger.info("=" * 60)
    
    if start_streaming_stt_callback:
        try:
            start_streaming_stt_callback(session_id)
            logger.info("=" * 60)
            logger.info(f"✅ [단계 12-2 완료] 브리지 서버: Streaming STT 시작 명령 처리 완료")
            logger.info(f"   Session ID: {session_id}")
            logger.info("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ [단계 12-2 실패] Streaming STT 시작 명령 처리 실패: {e}")
            logger.error("=" * 60)
    else:
        logger.warning("=" * 60)
        logger.warning("⚠️ Streaming STT 시작 콜백이 등록되지 않았습니다")
        logger.warning("=" * 60)

# 서비스 완료 신호 수신 (Python 3.13 → Python 3.10)
@sio.on('service_completed')
def handle_service_completed(sid, data):
    """Python 3.13에서 서비스 완료 신호 수신"""
    session_id = data.get("session_id", "")
    status = data.get("status", "")
    logger.info("=" * 60)
    logger.info(f"📥 [서비스 완료] 브리지 서버: 서비스 완료 신호 수신")
    logger.info(f"   Session ID: {session_id}, Status: {status}")
    logger.info("=" * 60)
    
    if service_completed_callback:
        try:
            service_completed_callback()
            logger.info("=" * 60)
            logger.info(f"✅ [서비스 완료] 브리지 서버: 서비스 완료 신호 처리 완료")
            logger.info("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ [서비스 완료 실패] 서비스 완료 신호 처리 실패: {e}")
            logger.error("=" * 60)
    else:
        logger.warning("=" * 60)
        logger.warning("⚠️ 서비스 완료 콜백이 등록되지 않았습니다")
        logger.warning("=" * 60)

# 모바일 음성 파일 재생 완료 신호 수신 (Python 3.13 → Python 3.10)
@sio.on('wakeword_audio_completed')
def handle_wakeword_audio_completed(sid, data):
    """Python 3.13에서 모바일 음성 파일 재생 완료 신호 수신"""
    logger.info("=" * 60)
    logger.info(f"📥 [모바일 음성 재생 완료] 브리지 서버: 모바일 음성 파일 재생 완료 신호 수신")
    logger.info("=" * 60)
    
    if wakeword_audio_completed_callback:
        try:
            wakeword_audio_completed_callback()
            logger.info("=" * 60)
            logger.info(f"✅ [모바일 음성 재생 완료] 브리지 서버: 모바일 음성 파일 재생 완료 신호 처리 완료")
            logger.info("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ [모바일 음성 재생 완료 실패] 모바일 음성 파일 재생 완료 신호 처리 실패: {e}")
            logger.error("=" * 60)
    else:
        logger.warning("=" * 60)
        logger.warning("⚠️ 모바일 음성 파일 재생 완료 콜백이 등록되지 않았습니다")
        logger.warning("=" * 60)

# Wakeword 감지 대기 시작 이벤트 수신 (Python 3.13 → Python 3.10)
wakeword_start_waiting_callback = None
mic_off_callback = None
mic_on_callback = None
mic_release_callback = None  # 마이크 장치 해제 콜백 (WebRTC 프로세스가 마이크를 사용할 수 있도록)
mic_acquire_callback = None  # 마이크 장치 재점유 콜백 (WebRTC 프로세스가 마이크를 해제한 후)

def set_wakeword_start_waiting_callback(callback):
    """Wakeword 감지 대기 시작 콜백 등록"""
    global wakeword_start_waiting_callback
    wakeword_start_waiting_callback = callback
    logger.info("✅ Wakeword 감지 대기 시작 콜백이 등록되었습니다")

def set_mic_off_callback(callback):
    """STT 목적 음성 수집 중지 콜백 등록"""
    global mic_off_callback
    mic_off_callback = callback
    logger.info("✅ STT 목적 음성 수집 중지 콜백이 등록되었습니다")

def set_mic_on_callback(callback):
    """STT 목적 음성 수집 재개 콜백 등록"""
    global mic_on_callback
    mic_on_callback = callback
    logger.info("✅ STT 목적 음성 수집 재개 콜백이 등록되었습니다")

def set_mic_release_callback(callback):
    """마이크 장치 해제 콜백 등록 (WebRTC 프로세스가 마이크를 사용할 수 있도록)"""
    global mic_release_callback
    mic_release_callback = callback
    logger.info("✅ 마이크 장치 해제 콜백이 등록되었습니다")

def set_mic_acquire_callback(callback):
    """마이크 장치 재점유 콜백 등록 (WebRTC 프로세스가 마이크를 해제한 후)"""
    global mic_acquire_callback
    mic_acquire_callback = callback
    logger.info("✅ 마이크 장치 재점유 콜백이 등록되었습니다")

@sio.on('wakeword_start_waiting')
def handle_wakeword_start_waiting(sid, data):
    """Wakeword 감지 대기 시작 이벤트 수신"""
    logger.info("=" * 60)
    logger.info(f"📥 브리지 서버: Wakeword 감지 대기 시작 이벤트 수신")
    logger.info("=" * 60)
    
    if wakeword_start_waiting_callback:
        try:
            wakeword_start_waiting_callback()
            logger.info("=" * 60)
            logger.info(f"✅ 브리지 서버: Wakeword 감지 대기 시작 이벤트 처리 완료")
            logger.info("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ 브리지 서버: Wakeword 감지 대기 시작 이벤트 처리 실패: {e}")
            logger.error("=" * 60)
    else:
        logger.warning("=" * 60)
        logger.warning("⚠️ Wakeword 감지 대기 시작 콜백이 등록되지 않았습니다")
        logger.warning("=" * 60)

@sio.on('mic_off')
def handle_mic_off(sid, data):
    """STT 목적 음성 수집 중지 이벤트 수신"""
    logger.info("=" * 60)
    logger.info(f"📥 브리지 서버: STT 목적 음성 수집 중지 이벤트 수신")
    logger.info("=" * 60)
    
    if mic_off_callback:
        try:
            mic_off_callback()
            logger.info("=" * 60)
            logger.info(f"✅ 브리지 서버: 마이크 OFF 이벤트 처리 완료")
            logger.info("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ 브리지 서버: 마이크 OFF 이벤트 처리 실패: {e}")
            logger.error("=" * 60)
    else:
        logger.warning("=" * 60)
        logger.warning("⚠️ 마이크 OFF 콜백이 등록되지 않았습니다")
        logger.warning("=" * 60)

@sio.on('mic_on')
def handle_mic_on(sid, data):
    """STT 목적 음성 수집 재개 이벤트 수신"""
    logger.info("=" * 60)
    logger.info(f"📥 브리지 서버: STT 목적 음성 수집 재개 이벤트 수신")
    logger.info("=" * 60)
    
    if mic_on_callback:
        try:
            mic_on_callback()
            logger.info("=" * 60)
            logger.info(f"✅ 브리지 서버: 마이크 ON 이벤트 처리 완료")
            logger.info("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"❌ 브리지 서버: 마이크 ON 이벤트 처리 실패: {e}")
            logger.error("=" * 60)
    else:
        logger.warning("=" * 60)
        logger.warning("⚠️ 마이크 ON 콜백이 등록되지 않았습니다")
        logger.warning("=" * 60)

@sio.on('handle_audio_stream')
def handle_audio_stream(sid, data):
    """WebRTC 오디오 스트리밍 시작/중지 이벤트 수신"""
    logger.info("=" * 60)
    logger.info(f"📥 브리지 서버: WebRTC 오디오 스트리밍 제어 이벤트 수신")
    logger.info(f"   데이터: {data}")
    logger.info("=" * 60)
    
    if data and data.get("start", False):
        # WebRTC 오디오 스트리밍 시작: 마이크 장치 해제
        logger.info("🎙️ WebRTC 오디오 스트리밍 시작 신호 수신")
        logger.info("   Python 3.10 프로세스가 마이크 장치를 해제합니다.")
        if mic_release_callback:
            try:
                mic_release_callback()
                logger.info("=" * 60)
                logger.info(f"✅ 브리지 서버: 마이크 장치 해제 완료 (WebRTC 프로세스가 사용할 수 있음)")
                logger.info("=" * 60)
            except Exception as e:
                logger.error("=" * 60)
                logger.error(f"❌ 브리지 서버: 마이크 장치 해제 실패: {e}")
                logger.error("=" * 60)
        else:
            logger.warning("=" * 60)
            logger.warning("⚠️ 마이크 장치 해제 콜백이 등록되지 않았습니다")
            logger.warning("=" * 60)
    else:
        # WebRTC 오디오 스트리밍 중지: 마이크 장치 재점유
        logger.info("🛑 WebRTC 오디오 스트리밍 중지 신호 수신")
        logger.info("   Python 3.10 프로세스가 마이크 장치를 재점유합니다.")
        if mic_acquire_callback:
            try:
                mic_acquire_callback()
                logger.info("=" * 60)
                logger.info(f"✅ 브리지 서버: 마이크 장치 재점유 완료")
                logger.info("=" * 60)
            except Exception as e:
                logger.error("=" * 60)
                logger.error(f"❌ 브리지 서버: 마이크 장치 재점유 실패: {e}")
                logger.error("=" * 60)
        else:
            logger.warning("=" * 60)
            logger.warning("⚠️ 마이크 장치 재점유 콜백이 등록되지 않았습니다")
            logger.warning("=" * 60)

# Wakeword 감지 이벤트 전송 함수 (Python 3.10에서 호출)
def send_wakeword_detected():
    """Wakeword 감지 이벤트를 브리지 클라이언트(3.13)에게 전송"""
    logger.info("=" * 60)
    logger.info(f"📤 [단계 2-1] 브리지 서버: Wakeword 감지 이벤트 전송 시작")
    logger.info(f"   연결된 클라이언트: {len(connected_clients)}개")
    logger.info("=" * 60)
    
    if not connected_clients:
        logger.warning("⚠️ 연결된 클라이언트가 없습니다. Wakeword 감지 이벤트를 전송할 수 없습니다.")
        return
    
    # 모든 연결된 클라이언트에게 전송
    for client_sid in list(connected_clients):  # 리스트로 복사하여 안전하게 순회
        try:
            sio.emit('wakeword_detected', {}, room=client_sid)
            logger.info(f"✅ 클라이언트 {client_sid[:10]}...에게 전송 완료")
        except Exception as e:
            logger.error(f"❌ 클라이언트 {client_sid}에게 전송 실패: {e}")
            connected_clients.discard(client_sid)  # 실패한 클라이언트 제거
    
    logger.info("=" * 60)
    logger.info("✅ [단계 2-1 완료] 브리지 서버: Wakeword 감지 이벤트 전송 완료")
    logger.info("=" * 60)

# 3️⃣ 외부에서 호출될 함수 (STT 결과 emit)
def send_stt_result(result: dict):
    """
    STT 결과를 브리지 클라이언트(3.13)에게 전송
    Args:
        result: {"type": "final", "text": "...", "confidence": 0.95}
    """
    logger.info("=" * 60)
    logger.info(f"📤 [단계 4] 브리지 서버: STT 결과 수신 및 전송 시작")
    logger.info(f"   타입: {result.get('type')}, 텍스트: {result.get('text', '')[:50]}...")
    logger.info(f"   연결된 클라이언트: {len(connected_clients)}개")
    logger.info("=" * 60)
    
    if not connected_clients:
        logger.warning("⚠️ 연결된 클라이언트가 없습니다. STT 결과를 전송할 수 없습니다.")
        return
    
    # 모든 연결된 클라이언트에게 전송
    for client_sid in list(connected_clients):  # 리스트로 복사하여 안전하게 순회
        try:
            sio.emit('stt_result', result, room=client_sid)
            logger.info(f"✅ 클라이언트 {client_sid[:10]}...에게 전송 완료")
        except Exception as e:
            logger.error(f"❌ 클라이언트 {client_sid}에게 전송 실패: {e}")
            connected_clients.discard(client_sid)  # 실패한 클라이언트 제거
    
    logger.info("=" * 60)
    logger.info("✅ [단계 4 완료] 브리지 서버: STT 결과 전송 완료")
    logger.info("=" * 60)

# 4️⃣ 서버 실행
def run_server(host='127.0.0.1', port=5050):
    from werkzeug.serving import WSGIRequestHandler, make_server
    logging.basicConfig(level=logging.INFO)
    logger.info(f"🚀 STT 브리지 서버 시작 (Socket.IO): ws://{host}:{port}")
    # threading 모드를 사용하므로 werkzeug 서버 사용
    server = make_server(host, port, app, request_handler=WSGIRequestHandler)
    server.serve_forever()

if __name__ == "__main__":
    run_server()