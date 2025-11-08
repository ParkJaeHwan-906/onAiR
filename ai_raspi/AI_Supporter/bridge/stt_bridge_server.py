"""
STT 브리지 서버 (Python 3.10용)
Python 3.10에서 실행되는 wakeword + STT 결과를 받아서
Python 3.13 프로세스로 전달하는 로컬 HTTP 서버
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 로컬 CORS 허용

# STT 결과를 저장할 큐 (메모리 기반)
stt_results_queue = []

@app.route('/health', methods=['GET'])
def health():
    """헬스 체크"""
    return jsonify({"status": "ok", "version": "3.10"})

@app.route('/stt/result', methods=['POST'])
def receive_stt_result():
    """
    STT 결과 수신 (Python 3.10에서 호출)
    
    Request Body:
    {
        "type": "final" | "interim" | "error",
        "text": "인식된 텍스트",
        "confidence": 0.95,
        "session_id": "uuid" (optional, streaming STT용)
    }
    """
    try:
        data = request.json
        logger.info(f"📥 STT 결과 수신: {data.get('type')} - {data.get('text', '')[:50]}...")
        
        # 큐에 추가
        stt_results_queue.append(data)
        
        # 큐 크기 제한 (메모리 보호)
        if len(stt_results_queue) > 100:
            stt_results_queue.pop(0)
            logger.warning("⚠️ STT 결과 큐가 가득참, 오래된 항목 제거")
        
        return jsonify({"status": "ok", "message": "STT 결과 수신 완료"})
    except Exception as e:
        logger.error(f"❌ STT 결과 수신 오류: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stt/poll', methods=['GET'])
def poll_stt_result():
    """
    STT 결과 폴링 (Python 3.13에서 호출)
    
    Returns:
    {
        "has_result": true/false,
        "result": {...} (있을 경우)
    }
    """
    try:
        if stt_results_queue:
            result = stt_results_queue.pop(0)
            logger.info(f"📤 STT 결과 전달: {result.get('type')} - {result.get('text', '')[:50]}...")
            return jsonify({
                "has_result": True,
                "result": result
            })
        else:
            return jsonify({
                "has_result": False,
                "result": None
            })
    except Exception as e:
        logger.error(f"❌ STT 결과 폴링 오류: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stt/queue/size', methods=['GET'])
def get_queue_size():
    """큐 크기 확인"""
    return jsonify({"size": len(stt_results_queue)})

def run_server(host='127.0.0.1', port=8888):
    """브리지 서버 실행"""
    logger.info(f"🚀 STT 브리지 서버 시작: http://{host}:{port}")
    logger.info("   Python 3.10에서 실행되는 wakeword + STT 결과를 수신합니다.")
    app.run(host=host, port=port, debug=False, threaded=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server()

