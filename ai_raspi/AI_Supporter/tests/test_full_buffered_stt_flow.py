"""
버퍼링 STT → Socket.IO → FastAPI → Phi-3 임베딩 → 모바일 분기 처리 전체 플로우 테스트

전체 플로우:
1. 라즈베리파이 → Socket.IO (`stt_result` 이벤트)
2. Socket.IO 서버 → FastAPI `/api/stt/buffered` (HTTP POST)
3. FastAPI → Phi-3 임베딩 추출
4. FastAPI → Socket.IO로 모바일에게 `embedding_result` 전송
5. 모바일 → Intent 분류 → 분기 처리

사용 방법:
    python tests/test_full_buffered_stt_flow.py --socketio-url http://localhost:8000 --fastapi-url http://localhost:8000
"""
import sys
import os
# Windows에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

import asyncio
import argparse
import logging
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import socketio
    import httpx
except ImportError as e:
    print(f"❌ 필요한 패키지가 설치되지 않았습니다: {e}")
    print("   pip install python-socketio httpx")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MobileClient:
    """모바일 클라이언트 시뮬레이션"""
    def __init__(self, socketio_url: str):
        self.socketio_url = socketio_url
        self.sio = socketio.AsyncClient()
        self.connected = False
        self.embedding_received = False
        self.embedding_result = None
        
        # 이벤트 핸들러 등록
        self.sio.on("connect", self.on_connect)
        self.sio.on("disconnect", self.on_disconnect)
        self.sio.on("embedding_result", self.on_embedding_result)
        self.sio.on("stt_result", self.on_stt_result)
    
    async def on_connect(self):
        logger.info("✅ 모바일 클라이언트: Socket.IO 서버 연결 성공")
        self.connected = True
        
        # 디바이스 등록
        await self.sio.emit("register_device", {"device": "mobile"})
        logger.info("📱 모바일 디바이스 등록 완료")
    
    async def on_disconnect(self):
        logger.info("❌ 모바일 클라이언트: Socket.IO 서버 연결 종료")
        self.connected = False
    
    async def on_stt_result(self, data):
        """STT 결과 수신 (레거시, embedding_result가 우선)"""
        logger.info(f"📩 [모바일] STT 결과 수신: {data}")
    
    async def on_embedding_result(self, data):
        """임베딩 결과 수신"""
        logger.info("="*70)
        logger.info("📩 [모바일] 임베딩 결과 수신!")
        logger.info(f"   텍스트: {data.get('text', 'N/A')}")
        logger.info(f"   차원: {data.get('dimension', 'N/A')}")
        logger.info(f"   신뢰도: {data.get('confidence', 'N/A')}")
        
        embedding = data.get('embedding', [])
        if embedding:
            logger.info(f"   임베딩 샘플 (처음 5개): {embedding[:5]}")
        
        self.embedding_received = True
        self.embedding_result = data
        
        # Intent 분류 시뮬레이션
        await self.simulate_intent_classification(data)
    
    async def simulate_intent_classification(self, embedding_data):
        """Intent 분류 시뮬레이션"""
        logger.info("\n" + "="*70)
        logger.info("🧠 [모바일] Intent 분류 시작...")
        
        text = embedding_data.get('text', '')
        embedding = embedding_data.get('embedding', [])
        
        # 간단한 키워드 기반 분류 (실제로는 ONNX 모델 사용)
        text_lower = text.lower()
        
        if '도움이 필요해' in text or '서포터' in text:
            intent = "AI_SUPPORTER"
            confidence = 0.85
        elif '연결' in text or '오퍼레이터' in text:
            intent = "OPERATOR"
            confidence = 0.80
        else:
            intent = "UNKNOWN"
            confidence = 0.50
        
        logger.info(f"✅ [모바일] Intent 분류 완료:")
        logger.info(f"   Intent: {intent}")
        logger.info(f"   신뢰도: {confidence:.2f}")
        
        # 분기 처리 시뮬레이션
        await self.simulate_dispatch(intent, confidence)
    
    async def simulate_dispatch(self, intent: str, confidence: float):
        """Intent 분기 처리 시뮬레이션"""
        logger.info("\n" + "="*70)
        logger.info("🚀 [모바일] Intent 분기 처리 시작...")
        
        if intent == "AI_SUPPORTER":
            logger.info("   → AI_SUPPORTER: Streaming STT 모드로 전환")
            logger.info("   → 라즈베리파이에 스트리밍 모드 요청 전송")
            # 실제로는 라즈베리파이로 스트리밍 모드 전환 요청을 보냄
        elif intent == "OPERATOR":
            logger.info("   → OPERATOR: 오퍼레이터 연결 요청")
            logger.info("   → 오퍼레이터 통신 연결 시도")
        else:
            logger.info(f"   → UNKNOWN: 처리 불가")
        
        logger.info("✅ [모바일] Intent 분기 처리 완료")
    
    async def connect(self):
        """Socket.IO 서버에 연결"""
        try:
            await self.sio.connect(self.socketio_url, socketio_path="/ws")
            return True
        except Exception as e:
            logger.error(f"❌ 모바일 클라이언트 연결 실패: {e}")
            return False
    
    async def disconnect(self):
        """Socket.IO 서버 연결 종료"""
        if self.connected:
            await self.sio.disconnect()


class RaspiClient:
    """라즈베리파이 클라이언트 시뮬레이션"""
    def __init__(self, socketio_url: str):
        self.socketio_url = socketio_url
        self.sio = socketio.AsyncClient()
        self.connected = False
    
    async def on_connect(self):
        logger.info("✅ 라즈베리파이 클라이언트: Socket.IO 서버 연결 성공")
        self.connected = True
        
        # 디바이스 등록
        await self.sio.emit("register_device", {"device": "raspi"})
        logger.info("🔌 라즈베리파이 디바이스 등록 완료")
    
    async def on_disconnect(self):
        logger.info("❌ 라즈베리파이 클라이언트: Socket.IO 서버 연결 종료")
        self.connected = False
    
    async def connect(self):
        """Socket.IO 서버에 연결"""
        # 이벤트 핸들러 등록
        self.sio.on("connect", self.on_connect)
        self.sio.on("disconnect", self.on_disconnect)
        
        try:
            await self.sio.connect(self.socketio_url, socketio_path="/ws")
            return True
        except Exception as e:
            logger.error(f"❌ 라즈베리파이 클라이언트 연결 실패: {e}")
            return False
    
    async def send_stt_result(self, text: str, stt_type: str = "final", confidence: float = 0.95):
        """STT 결과를 Socket.IO로 전송"""
        if not self.connected:
            logger.error("❌ 라즈베리파이 클라이언트가 연결되지 않았습니다.")
            return False
        
        stt_data = {
            "type": stt_type,
            "text": text,
            "confidence": confidence
        }
        
        try:
            await self.sio.emit("stt_result", stt_data)
            logger.info(f"📤 [라즈베리파이] STT 결과 전송:")
            logger.info(f"   타입: {stt_type}")
            logger.info(f"   텍스트: {text}")
            logger.info(f"   신뢰도: {confidence:.2f}")
            return True
        except Exception as e:
            logger.error(f"❌ STT 결과 전송 실패: {e}")
            return False
    
    async def disconnect(self):
        """Socket.IO 서버 연결 종료"""
        if self.connected:
            await self.sio.disconnect()


async def test_full_flow(text: str, socketio_url: str, fastapi_url: str):
    """전체 플로우 테스트"""
    logger.info("\n" + "="*70)
    logger.info("🔵 버퍼링 STT 전체 플로우 테스트 시작")
    logger.info("="*70)
    logger.info(f"테스트 텍스트: {text}")
    logger.info(f"Socket.IO 서버: {socketio_url}")
    logger.info(f"FastAPI 서버: {fastapi_url}")
    logger.info("="*70 + "\n")
    
    # 1. 모바일 클라이언트 연결
    logger.info("📱 [1단계] 모바일 클라이언트 연결 중...")
    mobile = MobileClient(socketio_url)
    mobile_connected = await mobile.connect()
    if not mobile_connected:
        logger.error("❌ 모바일 클라이언트 연결 실패!")
        return False
    
    await asyncio.sleep(1)  # 연결 안정화 대기
    
    # 2. 라즈베리파이 클라이언트 연결
    logger.info("\n🔌 [2단계] 라즈베리파이 클라이언트 연결 중...")
    raspi = RaspiClient(socketio_url)
    raspi_connected = await raspi.connect()
    if not raspi_connected:
        logger.error("❌ 라즈베리파이 클라이언트 연결 실패!")
        await mobile.disconnect()
        return False
    
    await asyncio.sleep(1)  # 연결 안정화 대기
    
    # 3. STT 결과 전송 (라즈베리파이 → Socket.IO)
    logger.info("\n📤 [3단계] 라즈베리파이에서 STT 결과 전송 중...")
    stt_sent = await raspi.send_stt_result(text, stt_type="final", confidence=0.95)
    if not stt_sent:
        logger.error("❌ STT 결과 전송 실패!")
        await raspi.disconnect()
        await mobile.disconnect()
        return False
    
    # 4. FastAPI 서버에서 임베딩 추출 및 모바일로 전송 대기
    logger.info("\n⏳ [4단계] FastAPI 서버 처리 대기 중...")
    logger.info("   (Socket.IO 서버 → FastAPI → Phi-3 임베딩 → 모바일 전송)")
    
    # 최대 30초 대기
    for i in range(30):
        await asyncio.sleep(1)
        if mobile.embedding_received:
            logger.info(f"✅ 임베딩 결과 수신 완료! ({i+1}초 소요)")
            break
    
    if not mobile.embedding_received:
        logger.error("❌ 임베딩 결과 수신 타임아웃 (30초 초과)")
        await raspi.disconnect()
        await mobile.disconnect()
        return False
    
    # 5. 정리
    logger.info("\n🧹 [5단계] 연결 정리 중...")
    await raspi.disconnect()
    await asyncio.sleep(1)
    await mobile.disconnect()
    
    logger.info("\n" + "="*70)
    logger.info("✅ 전체 플로우 테스트 성공!")
    logger.info("="*70)
    
    return True


async def main():
    parser = argparse.ArgumentParser(description='버퍼링 STT 전체 플로우 테스트')
    parser.add_argument('--text', type=str, default="AI 서포터 도움이 필요해",
                       help='테스트할 STT 텍스트')
    parser.add_argument('--socketio-url', type=str, default='http://localhost:8000',
                       help='Socket.IO 서버 URL')
    parser.add_argument('--fastapi-url', type=str, default='http://localhost:8000',
                       help='FastAPI 서버 URL')
    
    args = parser.parse_args()
    
    # 테스트 실행
    success = await test_full_flow(
        text=args.text,
        socketio_url=args.socketio_url,
        fastapi_url=args.fastapi_url
    )
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

