"""
실제 오디오 파일로 버퍼링 STT 실행 → 전체 플로우 테스트

전체 플로우:
1. 오디오 파일로 버퍼링 STT 실행
2. STT 결과 → Socket.IO 서버 (`stt_result` 이벤트)
3. Socket.IO 서버 → FastAPI `/api/stt/buffered` (HTTP POST)
4. FastAPI → Phi-3 임베딩 추출
5. FastAPI → Socket.IO로 모바일에게 `embedding_result` 전송
6. 모바일 → Intent 분류 → 분기 처리

사용 방법:
    python tests/test_buffered_stt_full_flow.py --audio tests/stt_buffer.wav --socketio-url http://localhost:8000
"""
import sys
import os
# Windows에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    try:
        import codecs
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass  # 인코딩 설정 실패 시 그대로 진행

import asyncio
import argparse
import logging
import wave
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import socketio
except ImportError as e:
    print(f"❌ 필요한 패키지가 설치되지 않았습니다: {e}")
    print("   pip install python-socketio")
    sys.exit(1)

from stt.gcp_stt_buffered import GcpBufferedStt
from stt.socketio_client import SocketIOClient
from server.websocket_manager import ConnectionManager
from config import settings
from tests.test_stt_with_audio_file import AudioFileStream

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
        @self.sio.on('connect')
        async def on_connect_handler():
            await self.on_connect()
        
        @self.sio.on('disconnect')
        async def on_disconnect_handler():
            await self.on_disconnect()
        
        @self.sio.on('embedding_result')
        async def on_embedding_result_handler(data):
            logger.info(f"🔔 [DEBUG] ⭐⭐⭐ embedding_result 이벤트 핸들러 호출됨! ⭐⭐⭐ data={data}")
            await self.on_embedding_result(data)
    
    async def on_connect(self):
        logger.info("✅ 모바일 클라이언트: Socket.IO 서버 연결 성공")
        self.connected = True
        
        # 디바이스 등록
        await self.sio.emit("register_device", {"device": "mobile"})
        logger.info("📱 모바일 디바이스 등록 완료")
    
    async def on_disconnect(self):
        logger.info("❌ 모바일 클라이언트: Socket.IO 서버 연결 종료")
        self.connected = False
    
    async def on_embedding_result(self, data):
        """임베딩 결과 수신"""
        logger.info("\n" + "="*70)
        logger.info("📩 [모바일] 임베딩 결과 수신!")
        logger.info(f"   텍스트: {data.get('text', 'N/A')}")
        logger.info(f"   차원: {data.get('dimension', 'N/A')}")
        logger.info(f"   신뢰도: {data.get('confidence', 'N/A')}")
        
        logger.info(f"🔔 [DEBUG] on_embedding_result 함수 호출됨! data keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
        
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
        
        if '도움이 필요해' in text or '서포터' in text or 'ai 서포터' in text or '에어컨 포터' in text:
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
            logger.info("   → Clarify 루프 시작 준비")
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
            # 연결 시도 (타임아웃 10초)
            await self.sio.connect(self.socketio_url, socketio_path="/ws", wait_timeout=10)
            # 연결 완료 대기
            await asyncio.sleep(0.5)
            return self.connected
        except Exception as e:
            logger.error(f"❌ 모바일 클라이언트 연결 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def disconnect(self):
        """Socket.IO 서버 연결 종료"""
        if self.connected:
            await self.sio.disconnect()


async def test_buffered_stt_full_flow(audio_file: str, socketio_url: str, buffer_duration: float = None):
    """버퍼링 STT 전체 플로우 테스트"""
    logger.info("\n" + "="*70)
    logger.info("🔵 버퍼링 STT 전체 플로우 테스트 시작")
    logger.info("="*70)
    logger.info(f"오디오 파일: {audio_file}")
    logger.info(f"Socket.IO 서버: {socketio_url}")
    logger.info("="*70 + "\n")
    
    # 1. 모바일 클라이언트 연결 (임베딩 수신 대기)
    logger.info("📱 [1단계] 모바일 클라이언트 연결 중...")
    mobile = MobileClient(socketio_url)
    mobile_connected = await mobile.connect()
    if not mobile_connected:
        logger.error("❌ 모바일 클라이언트 연결 실패!")
        return False
    
    await asyncio.sleep(1)  # 연결 안정화 대기
    
    # 2. 버퍼링 시간 설정
    if buffer_duration is not None:
        settings.STT_BUFFER_DURATION_SEC = buffer_duration
        logger.info(f"⚙️ 버퍼링 시간 설정: {buffer_duration}초")
    
    # 3. 연결 관리자 및 Socket.IO 클라이언트 초기화
    logger.info("\n🔌 [2단계] 라즈베리파이 STT 클라이언트 초기화 중...")
    manager = ConnectionManager()
    socketio_client = SocketIOClient(manager=manager)
    socketio_client.server_url = socketio_url
    manager.set_socketio_client(socketio_client)
    
    # Socket.IO 서버 연결
    logger.info(f"📡 Socket.IO 서버 연결 중: {socketio_url}")
    connected = await socketio_client.connect()
    if not connected:
        logger.error("❌ Socket.IO 서버 연결 실패!")
        await mobile.disconnect()
        return False
    
    logger.info("✅ Socket.IO 서버 연결 성공")
    
    # 4. 음성 파일 스트림 생성
    logger.info(f"\n📄 [3단계] 음성 파일 읽기 중...")
    audio_stream = AudioFileStream(audio_file)
    audio_stream.start()
    
    # 5. 버퍼링 STT 인스턴스 생성
    buffered_stt = GcpBufferedStt()
    
    # 6. 브로드캐스트 함수 (Socket.IO로 전송)
    async def broadcaster(msg):
        logger.info(f"\n📤 [라즈베리파이] STT 결과 전송:")
        logger.info(f"   타입: {msg.get('type')}")
        logger.info(f"   텍스트: {msg.get('text')}")
        logger.info(f"   신뢰도: {msg.get('confidence', 'N/A')}")
        
        # Socket.IO로 전송
        await manager.broadcast(msg)
        logger.info("   ✅ Socket.IO 전송 완료")
    
    try:
        # 7. 버퍼링 STT 실행 (비동기로 실행)
        logger.info(f"\n🎤 [4단계] 버퍼링 STT 처리 시작...")
        
        # STT 실행을 비동기 Task로 실행
        stt_task = asyncio.create_task(buffered_stt.run(audio_stream, broadcaster))
        
        # 최대 60초 대기 (STT 처리 + FastAPI 처리 + 모바일 수신)
        logger.info("⏳ 전체 플로우 처리 대기 중...")
        logger.info("   (STT → Socket.IO → FastAPI → Phi-3 임베딩 → 모바일 전송)")
        
        # STT 완료 대기
        await stt_task
        
        # 모바일이 임베딩을 수신할 때까지 대기 (최대 30초)
        for i in range(30):
            await asyncio.sleep(1)
            if mobile.embedding_received:
                logger.info(f"✅ 전체 플로우 완료! ({i+1}초 소요)")
                break
        
        if not mobile.embedding_received:
            logger.error("❌ 임베딩 결과 수신 타임아웃 (30초 초과)")
            logger.error("   FastAPI 서버가 실행 중인지 확인하세요.")
            return False
        
        # 8. 정리
        logger.info("\n🧹 [5단계] 연결 정리 중...")
        audio_stream.stop()
        await socketio_client.disconnect()
        await asyncio.sleep(1)
        await mobile.disconnect()
        
        logger.info("\n" + "="*70)
        logger.info("✅ 전체 플로우 테스트 성공!")
        logger.info("="*70)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        audio_stream.stop()
        try:
            await socketio_client.disconnect()
        except:
            pass
        try:
            await mobile.disconnect()
        except:
            pass


async def main():
    parser = argparse.ArgumentParser(description='실제 오디오 파일로 버퍼링 STT 전체 플로우 테스트')
    parser.add_argument('--audio', type=str, required=True,
                       help='테스트할 음성 파일 경로 (WAV 파일)')
    parser.add_argument('--socketio-url', type=str,
                       default='http://localhost:8000',
                       help='Socket.IO 서버 URL')
    parser.add_argument('--buffer-duration', type=float,
                       default=None,
                       help='버퍼링 시간 (초). 기본값: 설정 파일의 값')
    
    args = parser.parse_args()
    
    # 음성 파일 존재 확인
    if not os.path.exists(args.audio):
        logger.error(f"❌ 음성 파일을 찾을 수 없습니다: {args.audio}")
        return
    
    # 테스트 실행
    success = await test_buffered_stt_full_flow(
        audio_file=args.audio,
        socketio_url=args.socketio_url,
        buffer_duration=args.buffer_duration
    )
    
    if success:
        logger.info("\n🎉 모든 테스트 성공!")
        sys.exit(0)
    else:
        logger.error("\n❌ 테스트 실패!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

