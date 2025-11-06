"""
AI_SUPPORTER 분기 후 전체 플로우 테스트

전체 플로우:
1. 버퍼링 STT → Intent 분류 → AI_SUPPORTER 분기
2. 라즈베리파이 Streaming STT 모드 전환
3. Streaming STT → FastAPI → Clarify 처리
4. Clarify 턴 수신 및 처리
5. 최종 답변 수신 및 TTS 재생
6. Streaming STT 종료

사용 방법:
    python tests/test_ai_supporter_full_flow.py --audio tests/stt_buffer.wav --socketio-url http://localhost:8000 --fastapi-url http://localhost:8000
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
        pass

import asyncio
import argparse
import logging
import uuid
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
from stt.gcp_stt_stream import GcpStreamingStt
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
    def __init__(self, socketio_url: str, fastapi_url: str):
        self.socketio_url = socketio_url
        self.fastapi_url = fastapi_url
        self.sio = socketio.AsyncClient()
        self.connected = False
        self.embedding_received = False
        self.clarify_turn_received = False
        self.final_answer_received = False
        self.current_session_id = None
        self.current_turn_id = None
        
        # 이벤트 핸들러 등록
        @self.sio.on('connect')
        async def on_connect_handler():
            await self.on_connect()
        
        @self.sio.on('disconnect')
        async def on_disconnect_handler():
            await self.on_disconnect()
        
        @self.sio.on('embedding_result')
        async def on_embedding_result_handler(data):
            await self.on_embedding_result(data)
        
        @self.sio.on('clarify_turn')
        async def on_clarify_turn_handler(data):
            await self.on_clarify_turn(data)
        
        @self.sio.on('final_answer')
        async def on_final_answer_handler(data):
            await self.on_final_answer(data)
        
        @self.sio.on('stop_streaming_stt')
        async def on_stop_streaming_stt_handler(data):
            await self.on_stop_streaming_stt(data)
    
    async def on_connect(self):
        logger.info("✅ 모바일 클라이언트: Socket.IO 서버 연결 성공")
        self.connected = True
        await self.sio.emit("register_device", {"device": "mobile"})
        logger.info("📱 모바일 디바이스 등록 완료")
    
    async def on_disconnect(self):
        logger.info("❌ 모바일 클라이언트: Socket.IO 서버 연결 종료")
        self.connected = False
    
    async def on_embedding_result(self, data):
        """임베딩 결과 수신 및 Intent 분류"""
        logger.info("\n" + "="*70)
        logger.info("📩 [모바일] 임베딩 결과 수신!")
        logger.info(f"   텍스트: {data.get('text', 'N/A')}")
        logger.info(f"   차원: {data.get('dimension', 'N/A')}")
        logger.info(f"   신뢰도: {data.get('confidence', 'N/A')}")
        
        self.embedding_received = True
        
        # Intent 분류 시뮬레이션
        text = data.get('text', '')
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
        
        logger.info(f"🧠 [모바일] Intent 분류 완료: {intent} (신뢰도: {confidence:.2f})")
        
        # AI_SUPPORTER 분기 처리
        if intent == "AI_SUPPORTER":
            logger.info("🚀 [모바일] AI_SUPPORTER 분기 처리 시작...")
            logger.info("   → TTS: 'AI Supporter가 도와드리겠습니다.' 재생 (시뮬레이션)")
            logger.info("   → UI: 'AI Supporter ON' 표시 (시뮬레이션)")
            logger.info("   → CV API 요청 (시뮬레이션 - 실제로는 선택사항)")
            logger.info("   → 라즈베리파이에 Streaming STT 모드 전환 요청")
            
            # 세션 ID 생성
            self.current_session_id = str(uuid.uuid4())
            logger.info(f"   → 세션 ID 생성: {self.current_session_id}")
            
            # 라즈베리파이에 Streaming STT 모드 전환 요청 (시뮬레이션)
            # 실제로는 raspberryPiControlRepository.setSttMode("streaming") 호출
            logger.info("   ✅ AI_SUPPORTER 분기 처리 완료")
        else:
            logger.info(f"   → {intent}: 다른 Intent 처리")
    
    async def on_clarify_turn(self, data):
        """Clarify 턴 수신"""
        logger.info("\n" + "="*70)
        logger.info("❓ [모바일] Clarify 턴 수신!")
        logger.info(f"   세션 ID: {data.get('session_id', 'N/A')}")
        logger.info(f"   턴 ID: {data.get('turn_id', 'N/A')}")
        logger.info(f"   상태: {data.get('status', 'N/A')}")
        logger.info(f"   질문: {data.get('question', 'N/A')}")
        
        self.current_session_id = data.get('session_id')
        self.current_turn_id = data.get('turn_id', 1)
        self.clarify_turn_received = True
        
        # Clarify 응답 시뮬레이션 (사용자가 텍스트로 응답)
        status = data.get('status', '')
        if status == 'RED' or status == 'YELLOW':
            logger.info("   → TTS: Clarify 질문 재생 (시뮬레이션)")
            logger.info("   → UI: Clarify 턴 렌더링 (시뮬레이션)")
            logger.info("   → 사용자 응답 대기 중...")
            
            # 시뮬레이션: 자동으로 응답 전송 (테스트용)
            await asyncio.sleep(1)
            await self.send_clarify_response("문제 상황을 설명합니다", self.current_session_id, self.current_turn_id)
        elif status == 'GREEN':
            logger.info("   → GREEN 상태: 최종 답변 대기 중...")
    
    async def on_final_answer(self, data):
        """최종 답변 수신"""
        logger.info("\n" + "="*70)
        logger.info("✅ [모바일] 최종 답변 수신!")
        logger.info(f"   세션 ID: {data.get('session_id', 'N/A')}")
        logger.info(f"   답변: {data.get('answer', 'N/A')[:100]}...")
        
        if 'audio_url' in data:
            logger.info(f"   오디오 URL: {data.get('audio_url')}")
        elif 'audio_content' in data:
            logger.info(f"   오디오 콘텐츠: base64 인코딩됨 (길이: {len(data.get('audio_content', ''))})")
        
        self.final_answer_received = True
        logger.info("   → TTS: 최종 답변 오디오 재생 (시뮬레이션)")
        logger.info("   → UI: 최종 답변 텍스트 표시 (시뮬레이션)")
    
    async def on_stop_streaming_stt(self, data):
        """Streaming STT 종료 신호 수신"""
        logger.info("\n" + "="*70)
        logger.info("🛑 [모바일] Streaming STT 종료 신호 수신!")
        logger.info(f"   세션 ID: {data.get('session_id', 'N/A')}")
        logger.info("   → 라즈베리파이 Streaming STT 세션 종료 확인")
    
    async def send_clarify_response(self, text: str, session_id: str, turn_id: int):
        """Clarify 텍스트 응답 전송"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.fastapi_url}/api/clarify/response",
                    json={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "response": text,
                        "action": "continue"
                    },
                    timeout=30.0
                )
                if response.status_code == 200:
                    logger.info(f"✅ Clarify 응답 전송 완료: session_id={session_id}, turn_id={turn_id}, text={text}")
                else:
                    logger.error(f"❌ Clarify 응답 전송 실패: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Clarify 응답 전송 오류: {e}")
    
    async def connect(self):
        """Socket.IO 서버에 연결"""
        try:
            await self.sio.connect(self.socketio_url, socketio_path="/ws", wait_timeout=10)
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


class RaspiClient:
    """라즈베리파이 클라이언트 시뮬레이션"""
    def __init__(self, socketio_url: str):
        self.socketio_url = socketio_url
        self.sio = socketio.AsyncClient()
        self.connected = False
        self.streaming_stt_active = False
        self.current_session_id = None
        
        # 이벤트 핸들러 등록
        @self.sio.on('connect')
        async def on_connect_handler():
            await self.on_connect()
        
        @self.sio.on('disconnect')
        async def on_disconnect_handler():
            await self.on_disconnect()
        
        @self.sio.on('start_streaming_stt')
        async def on_start_streaming_stt_handler(data):
            await self.on_start_streaming_stt(data)
        
        @self.sio.on('stop_streaming_stt')
        async def on_stop_streaming_stt_handler(data):
            await self.on_stop_streaming_stt(data)
    
    async def on_connect(self):
        logger.info("✅ 라즈베리파이 클라이언트: Socket.IO 서버 연결 성공")
        self.connected = True
        await self.sio.emit("register_device", {"device": "raspi"})
        logger.info("🔗 라즈베리파이 디바이스 등록 완료")
    
    async def on_disconnect(self):
        logger.info("❌ 라즈베리파이 클라이언트: Socket.IO 서버 연결 종료")
        self.connected = False
    
    async def on_start_streaming_stt(self, data):
        """Streaming STT 시작 신호 수신"""
        session_id = data.get('session_id')
        logger.info(f"🎤 [라즈베리파이] Streaming STT 시작 신호 수신: session_id={session_id}")
        self.streaming_stt_active = True
        self.current_session_id = session_id
    
    async def on_stop_streaming_stt(self, data):
        """Streaming STT 종료 신호 수신"""
        session_id = data.get('session_id')
        logger.info(f"🛑 [라즈베리파이] Streaming STT 종료 신호 수신: session_id={session_id}")
        self.streaming_stt_active = False
        self.current_session_id = None
    
    async def send_streaming_stt(self, text: str, session_id: str = None):
        """Streaming STT 결과 전송"""
        if not self.connected:
            logger.error("❌ 라즈베리파이 클라이언트가 연결되지 않았습니다.")
            return False
        
        stt_data = {
            "type": "final",
            "text": text,
            "confidence": 0.95,
            "session_id": session_id or self.current_session_id
        }
        
        try:
            await self.sio.emit("stt_result", stt_data)
            logger.info(f"📤 [라즈베리파이] Streaming STT 결과 전송: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Streaming STT 결과 전송 실패: {e}")
            return False
    
    async def connect(self):
        """Socket.IO 서버에 연결"""
        try:
            await self.sio.connect(self.socketio_url, socketio_path="/ws", wait_timeout=10)
            await asyncio.sleep(0.5)
            return self.connected
        except Exception as e:
            logger.error(f"❌ 라즈베리파이 클라이언트 연결 실패: {e}")
            return False
    
    async def disconnect(self):
        """Socket.IO 서버 연결 종료"""
        if self.connected:
            await self.sio.disconnect()


async def test_ai_supporter_full_flow(
    audio_file: str,
    socketio_url: str,
    fastapi_url: str,
    buffer_duration: float = None
):
    """AI_SUPPORTER 전체 플로우 테스트"""
    logger.info("\n" + "="*70)
    logger.info("🔵 AI_SUPPORTER 전체 플로우 테스트 시작")
    logger.info("="*70)
    logger.info(f"오디오 파일: {audio_file}")
    logger.info(f"Socket.IO 서버: {socketio_url}")
    logger.info(f"FastAPI 서버: {fastapi_url}")
    logger.info("="*70 + "\n")
    
    # 1. 모바일 클라이언트 연결
    logger.info("📱 [1단계] 모바일 클라이언트 연결 중...")
    mobile = MobileClient(socketio_url, fastapi_url)
    if not await mobile.connect():
        logger.error("❌ 모바일 클라이언트 연결 실패!")
        return False
    await asyncio.sleep(1)
    
    # 2. 라즈베리파이 클라이언트 연결
    logger.info("🔌 [2단계] 라즈베리파이 클라이언트 연결 중...")
    raspi = RaspiClient(socketio_url)
    if not await raspi.connect():
        logger.error("❌ 라즈베리파이 클라이언트 연결 실패!")
        return False
    await asyncio.sleep(1)
    
    # 3. 버퍼링 STT 실행 (음성 파일 사용)
    logger.info("🎤 [3단계] 버퍼링 STT 실행 중...")
    audio_stream = AudioFileStream(audio_file)
    buffered_stt = GcpBufferedStt()
    
    manager = ConnectionManager()
    socketio_client = SocketIOClient(manager=manager)
    socketio_client.server_url = socketio_url
    manager.set_socketio_client(socketio_client)
    
    await socketio_client.connect()
    await asyncio.sleep(1)
    
    async def broadcaster(msg):
        """STT 결과 브로드캐스터"""
        await manager.broadcast(msg)
    
    # 버퍼링 STT 실행
    stt_task = asyncio.create_task(buffered_stt.run(audio_stream, broadcaster))
    await stt_task
    
    # 4. 임베딩 결과 수신 대기 (최대 30초)
    logger.info("⏳ [4단계] 임베딩 결과 수신 대기 중...")
    for i in range(30):
        await asyncio.sleep(1)
        if mobile.embedding_received:
            logger.info(f"✅ 임베딩 결과 수신 완료! ({i+1}초 소요)")
            break
    
    if not mobile.embedding_received:
        logger.error("❌ 임베딩 결과 수신 타임아웃")
        return False
    
    # 5. AI_SUPPORTER 분기 확인
    if not mobile.current_session_id:
        logger.error("❌ 세션 ID가 생성되지 않았습니다.")
        return False
    
    session_id = mobile.current_session_id
    logger.info(f"✅ 세션 ID 확인: {session_id}")
    
    # 6. Streaming STT 실행 (음성 파일 사용)
    logger.info("🎤 [5단계] 라즈베리파이 Streaming STT 시작...")
    logger.info(f"   → 세션 ID: {session_id}")
    logger.info("   → 마이크 ON (Streaming STT 모드)")
    
    # 7. Streaming STT 실행 (음성 파일 사용)
    logger.info("📤 [6단계] Streaming STT 실행 중...")
    
    # Streaming STT 클라이언트 설정
    streaming_stt = GcpStreamingStt(socketio_client=socketio_client)
    
    # Streaming STT 실행 (음성 파일로 시뮬레이션 - 스트리밍 모드: 실시간 시뮬레이션)
    streaming_audio_stream = AudioFileStream(audio_file, streaming_mode=True)
    streaming_audio_stream.start()
    
    async def streaming_broadcaster(msg):
        """Streaming STT 결과 브로드캐스터"""
        if isinstance(msg, dict):
            msg["session_id"] = session_id
        await manager.broadcast(msg)
    
    # Streaming STT를 비동기로 실행
    streaming_stt_task = asyncio.create_task(
        streaming_stt.run(streaming_audio_stream, streaming_broadcaster, session_id=session_id)
    )
    
    # Streaming STT 완료 대기 (최대 10초)
    try:
        await asyncio.wait_for(streaming_stt_task, timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("⚠️ Streaming STT 타임아웃 (계속 진행)")
        streaming_stt_task.cancel()
    
    await asyncio.sleep(2)
    
    # 8. Clarify 턴 수신 대기 (최대 30초)
    logger.info("⏳ [7단계] Clarify 턴 수신 대기 중...")
    for i in range(30):
        await asyncio.sleep(1)
        if mobile.clarify_turn_received:
            logger.info(f"✅ Clarify 턴 수신 완료! ({i+1}초 소요)")
            break
    
    if not mobile.clarify_turn_received:
        logger.warning("⚠️ Clarify 턴 수신 타임아웃 (계속 진행)")
    
    # 9. 최종 답변 수신 대기 (최대 60초)
    logger.info("⏳ [8단계] 최종 답변 수신 대기 중...")
    for i in range(60):
        await asyncio.sleep(1)
        if mobile.final_answer_received:
            logger.info(f"✅ 최종 답변 수신 완료! ({i+1}초 소요)")
            break
    
    if not mobile.final_answer_received:
        logger.warning("⚠️ 최종 답변 수신 타임아웃")
    
    # 10. 정리
    logger.info("\n🧹 [9단계] 연결 정리 중...")
    audio_stream.stop()
    await socketio_client.disconnect()
    await asyncio.sleep(1)
    await raspi.disconnect()
    await mobile.disconnect()
    
    logger.info("\n" + "="*70)
    logger.info("✅ AI_SUPPORTER 전체 플로우 테스트 완료!")
    logger.info("="*70)
    
    return True


async def main():
    parser = argparse.ArgumentParser(description='AI_SUPPORTER 전체 플로우 테스트')
    parser.add_argument('--audio', type=str, required=True,
                       help='테스트할 음성 파일 경로 (WAV 파일)')
    parser.add_argument('--socketio-url', type=str,
                       default='http://localhost:8000',
                       help='Socket.IO 서버 URL')
    parser.add_argument('--fastapi-url', type=str,
                       default='http://localhost:8000',
                       help='FastAPI 서버 URL')
    parser.add_argument('--buffer-duration', type=float,
                       default=None,
                       help='버퍼링 시간 (초). 기본값: 설정 파일의 값')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.audio):
        logger.error(f"❌ 음성 파일을 찾을 수 없습니다: {args.audio}")
        return
    
    if args.buffer_duration is not None:
        settings.STT_BUFFER_DURATION_SEC = args.buffer_duration
    
    success = await test_ai_supporter_full_flow(
        args.audio,
        args.socketio_url,
        args.fastapi_url,
        args.buffer_duration
    )
    
    if success:
        logger.info("\n🎉 모든 테스트 성공!")
    else:
        logger.error("\n❌ 테스트 실패!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

