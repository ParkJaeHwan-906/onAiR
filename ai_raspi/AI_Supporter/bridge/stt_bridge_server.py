import socketio
import logging

logger = logging.getLogger(__name__)

# 1️⃣ Socket.IO 서버 생성
sio = socketio.Server(cors_allowed_origins='*', async_mode='threading')
app = socketio.WSGIApp(sio)

# 2️⃣ 클라이언트 연결 이벤트
@sio.event
def connect(sid, environ):
    logger.info(f"✅ 브리지 클라이언트 연결됨: {sid}")

@sio.event
def disconnect(sid):
    logger.info(f"❌ 브리지 클라이언트 연결 종료: {sid}")

# 3️⃣ 외부에서 호출될 함수 (STT 결과 emit)
def send_stt_result(result: dict):
    """
    STT 결과를 브리지 클라이언트(3.13)에게 전송
    Args:
        result: {"type": "final", "text": "...", "confidence": 0.95}
    """
    logger.info(f"📤 STT 결과 전송: {result.get('type')} - {result.get('text', '')[:50]}...")
    sio.emit('stt_result', result)

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

    