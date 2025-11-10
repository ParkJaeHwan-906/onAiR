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

def set_start_streaming_stt_callback(callback):
    """Streaming STT 시작 콜백 설정 (Python 3.10에서 호출)"""
    global start_streaming_stt_callback
    start_streaming_stt_callback = callback
    logger.info("✅ Streaming STT 시작 콜백이 등록되었습니다")

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