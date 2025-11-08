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
import json
import requests
from stt.mic_stream import MicStream
from stt.gcp_stt_buffered import GcpBufferedStt
from stt.gcp_stt_stream import GcpStreamingStt
from stt.wakeword_hook import wait_for_wakeword, init_wakeword_detector, stop_wakeword_detector
from bridge.stt_bridge_server import run_server as run_bridge_server
from config import settings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 브리지 서버 URL (로컬)
BRIDGE_SERVER_URL = "http://127.0.0.1:8888"

def send_stt_result_to_bridge(stt_data: dict):
    """
    STT 결과를 브리지 서버로 전송
    
    Args:
        stt_data: STT 결과 딕셔너리
            예: {"type": "final", "text": "안녕하세요", "confidence": 0.95}
    """
    try:
        response = requests.post(
            f"{BRIDGE_SERVER_URL}/stt/result",
            json=stt_data,
            timeout=1
        )
        if response.status_code == 200:
            logger.info(f"✅ STT 결과 브리지 서버로 전송 완료: {stt_data.get('type')} - {stt_data.get('text', '')[:50]}...")
        else:
            logger.warning(f"⚠️ 브리지 서버 응답 오류: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ 브리지 서버 전송 오류: {e}")

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
        target=run_bridge_server,
        args=('127.0.0.1', 8888),
        daemon=True
    )
    bridge_thread.start()
    logger.info("🚀 브리지 서버 시작 (포트 8888)")
    logger.info("   Python 3.13에서 브리지 클라이언트가 연결할 수 있습니다.")
    
    # 브리지 서버가 시작될 때까지 잠시 대기
    import time
    time.sleep(1)
    
    # 마이크 초기화 및 시작 (항상 켜져있음)
    mic = MicStream()
    mic.start()  # 스트림 생성 및 시작 (마이크 ON)
    logger.info("🔊 마이크 ON (항상 활성 상태)")
    
    # STT 인스턴스 생성
    buffered_stt = GcpBufferedStt()
    streaming_stt = GcpStreamingStt()
    
    # Wakeword 감지기 초기화
    init_wakeword_detector()
    
    async def broadcast(msg):
        """STT 결과를 브리지 서버로 전송"""
        send_stt_result_to_bridge(msg)
    
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
                # 마이크 다시 활성화 (Intent 분류 중간에 OFF되었으므로)
                if not mic.stream.is_active():
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
            if not mic.stream.is_active():
                mic.resume()
    
    # 이벤트 루프 생성
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    logger.info("🎧 STT 루프 대기 시작 (마이크 ON, Wakeword 감지 중)")
    logger.info("📌 Python 3.10에서 실행 중 (wakeword + STT)")
    logger.info(f"📡 브리지 서버: {BRIDGE_SERVER_URL}")
    
    try:
        while True:
            # ① 대기 상태 (마이크 ON, Wakeword 감지 중)
            # ② Wakeword 감지 대기
            if wait_for_wakeword():
                logger.info("🚀 Wakeword 감지됨: STT 세션 시작")
                
                # ③~⑦ STT 세션 실행 (모드에 따라 버퍼링/스트리밍)
                loop.run_until_complete(stt_session())
                
                logger.info("🟢 STT 세션 종료, 다시 대기 중... (마이크 ON, 다음 Wakeword 대기)")
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

