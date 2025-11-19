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
    # 로그 최소화: 콜백 등록 로그 제거

def set_service_completed_callback(callback):
    """서비스 완료 콜백 설정 (Python 3.10에서 호출)"""
    global service_completed_callback
    service_completed_callback = callback
    # 로그 최소화: 콜백 등록 로그 제거

def set_wakeword_audio_completed_callback(callback):
    """모바일 음성 파일 재생 완료 콜백 설정 (Python 3.10에서 호출)"""
    global wakeword_audio_completed_callback
    wakeword_audio_completed_callback = callback
    # 로그 최소화: 콜백 등록 로그 제거

# 2️⃣ 클라이언트 연결 이벤트
@sio.event
def connect(sid, environ):
    connected_clients.add(sid)
    # 로그 최소화: 정상 연결 시 로그 제거

@sio.event
def disconnect(sid):
    connected_clients.discard(sid)
    logger.warning(f"⚠️ 브리지 클라이언트 연결 종료: {sid}")

# 버퍼링 STT 세션 종료 명령 수신 (Python 3.13 → Python 3.10)
stop_buffered_stt_callback = None

def set_stop_buffered_stt_callback(callback):
    """버퍼링 STT 세션 종료 콜백 설정 (Python 3.10에서 호출)"""
    global stop_buffered_stt_callback
    stop_buffered_stt_callback = callback
    # 로그 최소화: 콜백 등록 로그 제거

@sio.on('stop_buffered_stt')
def handle_stop_buffered_stt(sid, data):
    """Python 3.13에서 버퍼링 STT 세션 종료 명령 수신"""
    reason = data.get("reason", "unknown")
    
    if stop_buffered_stt_callback:
        try:
            stop_buffered_stt_callback(reason)
            # 로그 최소화: 정상 처리 시 로그 제거
        except Exception as e:
            logger.error(f"❌ 버퍼링 STT 세션 종료 명령 처리 실패: {e}")
    else:
        logger.warning("⚠️ 버퍼링 STT 세션 종료 콜백이 등록되지 않았습니다")

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
    logger.info("📥 모바일 음성 파일 재생 완료 신호 수신")
    
    if wakeword_audio_completed_callback:
        try:
            wakeword_audio_completed_callback()
        except Exception as e:
            logger.error(f"❌ 모바일 음성 재생 완료 신호 처리 실패: {e}")
    else:
        logger.warning("⚠️ 모바일 음성 재생 완료 콜백 미등록")

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
    # 로그 최소화: 콜백 등록 로그 제거

def set_mic_off_callback(callback):
    """STT 목적 음성 수집 중지 콜백 등록"""
    global mic_off_callback
    mic_off_callback = callback
    # 로그 최소화: 콜백 등록 로그 제거

def set_mic_on_callback(callback):
    """STT 목적 음성 수집 재개 콜백 등록"""
    global mic_on_callback
    mic_on_callback = callback
    # 로그 최소화: 콜백 등록 로그 제거

def set_mic_release_callback(callback):
    """마이크 장치 해제 콜백 등록 (WebRTC 프로세스가 마이크를 사용할 수 있도록)"""
    global mic_release_callback
    mic_release_callback = callback
    # 로그 최소화: 콜백 등록 로그 제거

def set_mic_acquire_callback(callback):
    """마이크 장치 재점유 콜백 등록 (WebRTC 프로세스가 마이크를 해제한 후)"""
    global mic_acquire_callback
    mic_acquire_callback = callback
    # 로그 최소화: 콜백 등록 로그 제거

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
    if data and data.get("start", False):
        # WebRTC 오디오 스트리밍 시작: 마이크 장치 해제
        if mic_release_callback:
            try:
                mic_release_callback()
                # 로그 최소화: 정상 처리 시 로그 제거
            except Exception as e:
                logger.error(f"❌ 마이크 장치 해제 실패: {e}")
        else:
            logger.warning("⚠️ 마이크 장치 해제 콜백이 등록되지 않았습니다")
    else:
        # WebRTC 오디오 스트리밍 중지: 마이크 장치 재점유 및 Wakeword 감지 대기 시작
        if mic_acquire_callback:
            try:
                mic_acquire_callback()  # 마이크 재점유 및 Wakeword 감지기 재활성화
                # 로그 최소화: 정상 처리 시 로그 제거
            except Exception as e:
                logger.error(f"❌ 마이크 장치 재점유 실패: {e}")
        else:
            logger.warning("⚠️ 마이크 장치 재점유 콜백이 등록되지 않았습니다")
        
        # Wakeword 감지 대기 시작 (이미 mic_acquire_callback에서 처리되지만, 안전을 위해 별도로도 호출)
        if wakeword_start_waiting_callback:
            try:
                wakeword_start_waiting_callback()
                # 로그 최소화: 정상 처리 시 로그 제거
            except Exception as e:
                # 로그 최소화: 무시 가능한 오류는 로그 제거
                pass

# Wakeword 감지 대기 준비 완료 이벤트 전송 함수 (Python 3.10에서 호출)
def send_wakeword_waiting_ready():
    """Wakeword 감지 대기 상태로 복귀 완료 이벤트를 브리지 클라이언트(3.13)에게 전송"""
    if not connected_clients:
        # 로그 최소화: 연결 상태는 주기적으로 확인하므로 경고 로그 제거
        return False
    
    success_count = 0
    for client_sid in list(connected_clients):
        try:
            sio.emit('wakeword_waiting_ready', {}, room=client_sid)
            success_count += 1
            # 로그 최소화: 정상 전송 시 로그 제거
        except Exception as e:
            logger.error(f"❌ Wakeword 대기 준비 이벤트 전송 실패: {e}")
    
    return success_count > 0

# Wakeword 감지 이벤트 전송 함수 (Python 3.10에서 호출)
def send_wakeword_detected():
    """Wakeword 감지 이벤트를 브리지 클라이언트(3.13)에게 전송"""
    if not connected_clients:
        # 로그 최소화: 연결 상태는 주기적으로 확인하므로 경고 로그 제거
        return False
    
    success_count = 0
    for client_sid in list(connected_clients):
        try:
            sio.emit('wakeword_detected', {}, room=client_sid)
            success_count += 1
            # 로그 최소화: 정상 전송 시 로그 제거
        except Exception as e:
            logger.error(f"❌ Wakeword 이벤트 전송 실패: {e}")
            connected_clients.discard(client_sid)
    
    return success_count > 0

# 3️⃣ 외부에서 호출될 함수 (STT 결과 emit)
def send_stt_result(result: dict):
    """STT 결과를 브리지 클라이언트(3.13)에게 전송"""
    if not connected_clients:
        # 로그 최소화: 연결 상태는 주기적으로 확인하므로 경고 로그 제거
        return False
    
    success = False
    for client_sid in list(connected_clients):
        try:
            sio.emit('stt_result', result, room=client_sid)
            success = True
            # 로그 최소화: 정상 전송 시 로그 제거
        except Exception as e:
            logger.error(f"❌ STT 결과 전송 실패: {e}")
            connected_clients.discard(client_sid)
    
    return success

# 4️⃣ 서버 실행
def run_server(host='127.0.0.1', port=5050):
    from werkzeug.serving import WSGIRequestHandler, make_server
    import socket
    logging.basicConfig(level=logging.INFO)
    logger.info(f"🚀 STT 브리지 서버 시작 (Socket.IO): ws://{host}:{port}")
    
    # 포트가 이미 사용 중인지 확인
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            logger.error("=" * 60)
            logger.error(f"❌ 포트 {port}가 이미 사용 중입니다!")
            logger.error("   해결 방법:")
            logger.error(f"   1. 포트를 사용 중인 프로세스 확인: sudo lsof -i :{port}")
            logger.error(f"   2. 프로세스 종료: sudo kill -9 <PID>")
            logger.error(f"   3. 또는 모든 main_py310.py 프로세스 종료: pkill -f main_py310.py")
            logger.error("=" * 60)
            raise OSError(f"Port {port} is already in use")
    except socket.error as e:
        # 포트 확인 중 오류 발생 (무시 가능)
        logger.debug(f"포트 확인 중 오류 (무시 가능): {e}")
    
    # threading 모드를 사용하므로 werkzeug 서버 사용
    try:
        server = make_server(host, port, app, request_handler=WSGIRequestHandler)
        logger.info(f"✅ 브리지 서버 바인딩 성공: ws://{host}:{port}")
        server.serve_forever()
    except OSError as e:
        if "Address already in use" in str(e) or "already in use" in str(e).lower():
            logger.error("=" * 60)
            logger.error(f"❌ 포트 {port} 바인딩 실패: 포트가 이미 사용 중입니다")
            logger.error("   해결 방법:")
            logger.error(f"   1. 포트를 사용 중인 프로세스 확인: sudo lsof -i :{port}")
            logger.error(f"   2. 프로세스 종료: sudo kill -9 <PID>")
            logger.error(f"   3. 또는 모든 main_py310.py 프로세스 종료: pkill -f main_py310.py")
            logger.error("=" * 60)
        raise

if __name__ == "__main__":
    run_server()