"""
음성 파일 기반 전체 플로우 테스트

1. 버퍼링 STT 테스트 (음성 파일 → STT → Intent 분류)
2. AI_SUPPORTER 분기 플로우 테스트 (CV 탐지 실패 → Streaming STT → Clarify 루프)
3. OPERATOR 분기 플로우 테스트 (LiveKit 연결)

사용 방법:
    # AI_SUPPORTER 분기 테스트
    python tests/test_audio_file_full_flow.py \
        --buffered-audio tests/stt_buffer.wav \
        --streaming-audio tests/stt_stream.wav \
        --socketio-url http://localhost:5000 \
        --fastapi-url http://localhost:8000 \
        --test-type ai_supporter
    
    # OPERATOR 분기 테스트
    python tests/test_audio_file_full_flow.py \
        --buffered-audio tests/stt_buffer.wav \
        --socketio-url http://localhost:5000 \
        --fastapi-url http://localhost:8000 \
        --spring-url https://onair.ai.kr/api \
        --access-token YOUR_TOKEN \
        --test-type operator
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
from typing import Optional

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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MobileClient:
    """모바일 클라이언트 시뮬레이션"""
    def __init__(self, socketio_url: str):
        self.socketio_url = socketio_url
        self.sio = socketio.AsyncClient()
        self.connected = False
        self.sid = None
        
        # 수신 이벤트 추적
        self.intent_result_received = False
        self.intent_result: Optional[dict] = None
        self.cv_detection_failed_received = False
        self.clarify_qa_turn_received = False
        self.clarify_qa_turns: list = []
        self.final_answer_received = False
        self.final_answer: Optional[dict] = None
        self.start_sse_connection_received = False
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Socket.IO 이벤트 핸들러 설정"""
        
        @self.sio.event
        async def connect():
            logger.info("✅ [모바일] Socket.IO 서버 연결 성공")
            self.connected = True
            self.sid = self.sio.sid
            await self.sio.emit("register_device", {"device": "mobile"})
        
        @self.sio.event
        async def disconnect():
            logger.info("🔌 [모바일] Socket.IO 서버 연결 종료")
            self.connected = False
        
        @self.sio.on("intent_result")
        async def on_intent_result(data):
            logger.info(f"📩 [모바일] Intent 결과 수신: {data}")
            self.intent_result_received = True
            self.intent_result = data
        
        @self.sio.on("start_sse_connection")
        async def on_start_sse_connection(data):
            logger.info(f"📡 [모바일] SSE 연결 시작 요청 수신: {data}")
            self.start_sse_connection_received = True
        
        @self.sio.on("cv_detection_failed")
        async def on_cv_detection_failed(data):
            logger.info(f"⚠️ [모바일] CV 탐지 실패 수신: {data}")
            self.cv_detection_failed_received = True
        
        @self.sio.on("clarify_qa_turn")
        async def on_clarify_qa_turn(data):
            logger.info(f"💬 [모바일] Clarify 질문/답변 턴 수신:")
            logger.info(f"   세션 ID: {data.get('session_id')}")
            logger.info(f"   턴 ID: {data.get('turn_id')}")
            logger.info(f"   작업자 질문: {data.get('user_question')}")
            logger.info(f"   LLM 답변: {data.get('llm_answer')}")
            logger.info(f"   추가 구체화 필요: {data.get('need_clarify')}")
            self.clarify_qa_turn_received = True
            self.clarify_qa_turns.append(data)
        
        @self.sio.on("final_answer")
        async def on_final_answer(data):
            logger.info(f"✅ [모바일] 최종 답변 수신:")
            logger.info(f"   세션 ID: {data.get('session_id')}")
            logger.info(f"   답변: {data.get('answer', '')[:100]}...")
            self.final_answer_received = True
            self.final_answer = data
    
    async def connect(self):
        """Socket.IO 서버에 연결"""
        try:
            await self.sio.connect(self.socketio_url, socketio_path="/ws", wait_timeout=30)
            await asyncio.sleep(1)
            return self.connected
        except Exception as e:
            logger.error(f"❌ [모바일] 연결 실패: {e}")
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
        self.sid = None
        self.cv_detection_failed_received = False
        self.current_session_id: Optional[str] = None
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Socket.IO 이벤트 핸들러 설정"""
        
        @self.sio.event
        async def connect():
            logger.info("✅ [라즈베리파이] Socket.IO 서버 연결 성공")
            self.connected = True
            self.sid = self.sio.sid
            await self.sio.emit("register_device", {"device": "raspi"})
        
        @self.sio.event
        async def disconnect():
            logger.info("🔌 [라즈베리파이] Socket.IO 서버 연결 종료")
            self.connected = False
        
        @self.sio.on("cv_detection_failed")
        async def on_cv_detection_failed(data):
            logger.info(f"⚠️ [라즈베리파이] CV 탐지 실패 수신: {data}")
            self.cv_detection_failed_received = True
            # Streaming STT 세션 시작 (시뮬레이션)
            logger.info("🎤 [라즈베리파이] Streaming STT 세션 시작 (시뮬레이션)")
            self.current_session_id = str(uuid.uuid4())
    
    async def send_buffered_stt(self, text: str, confidence: float = 0.95):
        """버퍼링 STT 결과 전송"""
        if not self.connected:
            logger.error("❌ [라즈베리파이] 연결되지 않았습니다.")
            return False
        
        stt_data = {
            "type": "final",
            "text": text,
            "confidence": confidence
        }
        
        try:
            await self.sio.emit("stt_result", stt_data)
            logger.info(f"📤 [라즈베리파이] 버퍼링 STT 전송: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ [라즈베리파이] STT 전송 실패: {e}")
            return False
    
    async def send_streaming_stt(self, text: str, session_id: str = None):
        """Streaming STT 결과 전송"""
        if not self.connected:
            logger.error("❌ [라즈베리파이] 연결되지 않았습니다.")
            return False
        
        stt_data = {
            "type": "final",
            "text": text,
            "confidence": 0.95,
            "session_id": session_id or self.current_session_id
        }
        
        try:
            await self.sio.emit("stt_result", stt_data)
            logger.info(f"📤 [라즈베리파이] Streaming STT 전송: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ [라즈베리파이] Streaming STT 전송 실패: {e}")
            return False
    
    async def connect(self):
        """Socket.IO 서버에 연결"""
        try:
            await self.sio.connect(self.socketio_url, socketio_path="/ws", wait_timeout=30)
            await asyncio.sleep(1)
            return self.connected
        except Exception as e:
            logger.error(f"❌ [라즈베리파이] 연결 실패: {e}")
            return False
    
    async def disconnect(self):
        """Socket.IO 서버 연결 종료"""
        if self.connected:
            await self.sio.disconnect()


async def test_ai_supporter_flow(
    buffered_audio_file: str,
    streaming_audio_file: str,
    socketio_url: str,
    fastapi_url: str
):
    """AI_SUPPORTER 분기 플로우 테스트"""
    logger.info("\n" + "="*70)
    logger.info("🔵 AI_SUPPORTER 분기 플로우 테스트 시작")
    logger.info("="*70)
    logger.info(f"버퍼링 STT 음성 파일: {buffered_audio_file}")
    logger.info(f"Streaming STT 음성 파일: {streaming_audio_file}")
    logger.info(f"Socket.IO 서버: {socketio_url}")
    logger.info(f"FastAPI 서버: {fastapi_url}")
    logger.info("="*70 + "\n")
    
    # 1. 모바일 클라이언트 연결
    logger.info("📱 [1단계] 모바일 클라이언트 연결 중...")
    mobile = MobileClient(socketio_url)
    if not await mobile.connect():
        logger.error("❌ 모바일 클라이언트 연결 실패!")
        return False
    
    await asyncio.sleep(1)
    
    # 2. 라즈베리파이 클라이언트 연결
    logger.info("\n🔌 [2단계] 라즈베리파이 클라이언트 연결 중...")
    raspi = RaspiClient(socketio_url)
    if not await raspi.connect():
        logger.error("❌ 라즈베리파이 클라이언트 연결 실패!")
        await mobile.disconnect()
        return False
    
    await asyncio.sleep(1)
    
    # 3. 버퍼링 STT 처리 (음성 파일 → STT → Intent 분류)
    logger.info("\n🎤 [3단계] 버퍼링 STT 처리 시작...")
    try:
        from stt.gcp_stt_buffered import GcpBufferedStt
        from tests.test_stt_with_audio_file import AudioFileStream
        
        # 음성 파일 스트림 생성
        audio_stream = AudioFileStream(buffered_audio_file)
        audio_stream.start()
        
        # 버퍼링 STT 인스턴스 생성
        buffered_stt = GcpBufferedStt()
        
        # 브로드캐스트 함수 (Socket.IO로 전송)
        async def broadcaster(msg):
            if msg.get("type") == "final":
                await raspi.sio.emit("stt_result", msg)
                logger.info(f"📤 [라즈베리파이] 버퍼링 STT 전송: {msg.get('text', '')[:50]}...")
        
        # 버퍼링 STT 실행
        stt_task = asyncio.create_task(buffered_stt.run(audio_stream, broadcaster))
        await stt_task
        
        audio_stream.stop()
        
    except Exception as e:
        logger.error(f"❌ 버퍼링 STT 처리 실패: {e}")
        import traceback
        traceback.print_exc()
        await raspi.disconnect()
        await mobile.disconnect()
        return False
    
    # 4. Intent 결과 및 CV 탐지 실패 이벤트 수신 대기
    logger.info("\n⏳ [4단계] Intent 분류 및 CV 모델 실행 대기 중...")
    for i in range(10):
        await asyncio.sleep(1)
        if mobile.intent_result_received and mobile.cv_detection_failed_received:
            logger.info(f"✅ Intent 분류 및 CV 탐지 실패 수신 완료! ({i+1}초 소요)")
            break
    
    if not mobile.intent_result_received:
        logger.error("❌ Intent 결과 수신 타임아웃")
        await raspi.disconnect()
        await mobile.disconnect()
        return False
    
    if mobile.intent_result.get("intent") != "AI_SUPPORTER":
        logger.warning(f"⚠️ Intent가 AI_SUPPORTER가 아닙니다: {mobile.intent_result.get('intent')}")
        logger.info("   테스트를 계속 진행합니다...")
    
    if not mobile.cv_detection_failed_received:
        logger.warning("⚠️ CV 탐지 실패 이벤트를 수신하지 못했습니다.")
        logger.info("   테스트를 계속 진행합니다...")
    
    # 5. Streaming STT 세션 시작 (CV 탐지 실패 후)
    logger.info("\n🎤 [5단계] Streaming STT 세션 시작...")
    if not raspi.cv_detection_failed_received:
        logger.warning("⚠️ CV 탐지 실패 이벤트를 수신하지 못해 세션 ID를 생성합니다.")
        raspi.current_session_id = str(uuid.uuid4())
    
    # Streaming STT 처리 (음성 파일 사용)
    try:
        from stt.gcp_stt_stream import GcpStreamingStt
        
        # 음성 파일 스트림 생성
        streaming_audio_stream = AudioFileStream(streaming_audio_file)
        streaming_audio_stream.start()
        
        # Streaming STT 인스턴스 생성
        streaming_stt = GcpStreamingStt()
        streaming_stt.socketio_client = raspi.sio
        streaming_stt.session_id = raspi.current_session_id
        
        # 브로드캐스트 함수 (Socket.IO로 전송)
        async def streaming_broadcaster(msg):
            if msg.get("type") == "final":
                await raspi.send_streaming_stt(
                    msg.get("text", ""),
                    session_id=raspi.current_session_id
                )
        
        # Streaming STT 실행
        logger.info("   Streaming STT 처리 중...")
        streaming_task = asyncio.create_task(
            streaming_stt.run(streaming_audio_stream, broadcaster=streaming_broadcaster, session_id=raspi.current_session_id)
        )
        
        # 최대 30초 대기
        try:
            await asyncio.wait_for(streaming_task, timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Streaming STT 타임아웃 (30초 초과)")
        
        streaming_audio_stream.stop()
        
    except Exception as e:
        logger.error(f"❌ Streaming STT 처리 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Clarify 질문/답변 턴 및 최종 답변 수신 대기
    logger.info("\n⏳ [6단계] Clarify 루프 및 최종 답변 대기 중...")
    for i in range(30):
        await asyncio.sleep(1)
        if mobile.final_answer_received:
            logger.info(f"✅ 최종 답변 수신 완료! ({i+1}초 소요)")
            break
        if mobile.clarify_qa_turn_received:
            logger.info(f"💬 Clarify 질문/답변 턴 수신: {len(mobile.clarify_qa_turns)}개")
    
    # 7. 결과 요약
    logger.info("\n" + "="*70)
    logger.info("📊 테스트 결과 요약")
    logger.info("="*70)
    logger.info(f"✅ Intent 결과 수신: {mobile.intent_result_received}")
    if mobile.intent_result:
        logger.info(f"   Intent: {mobile.intent_result.get('intent')}")
        logger.info(f"   신뢰도: {mobile.intent_result.get('confidence', 0):.2f}")
    logger.info(f"✅ CV 탐지 실패 수신: {mobile.cv_detection_failed_received}")
    logger.info(f"✅ Clarify 질문/답변 턴 수신: {mobile.clarify_qa_turn_received} ({len(mobile.clarify_qa_turns)}개)")
    logger.info(f"✅ 최종 답변 수신: {mobile.final_answer_received}")
    if mobile.final_answer:
        logger.info(f"   답변: {mobile.final_answer.get('answer', '')[:100]}...")
    logger.info("="*70 + "\n")
    
    # 8. 정리
    logger.info("🧹 [7단계] 연결 정리 중...")
    await raspi.disconnect()
    await mobile.disconnect()
    
    success = (
        mobile.intent_result_received and
        mobile.cv_detection_failed_received and
        (mobile.clarify_qa_turn_received or mobile.final_answer_received)
    )
    
    if success:
        logger.info("\n✅ AI_SUPPORTER 분기 플로우 테스트 성공!")
    else:
        logger.error("\n❌ AI_SUPPORTER 분기 플로우 테스트 실패!")
    
    return success


async def test_operator_flow(
    buffered_audio_file: str,
    socketio_url: str,
    fastapi_url: str,
    spring_url: str,
    access_token: str
):
    """OPERATOR 분기 플로우 테스트 (LiveKit 연결)"""
    logger.info("\n" + "="*70)
    logger.info("🔴 OPERATOR 분기 플로우 테스트 시작")
    logger.info("="*70)
    logger.info(f"버퍼링 STT 음성 파일: {buffered_audio_file}")
    logger.info(f"Socket.IO 서버: {socketio_url}")
    logger.info(f"FastAPI 서버: {fastapi_url}")
    logger.info(f"Spring 서버: {spring_url}")
    logger.info("="*70 + "\n")
    
    # 1. 모바일 클라이언트 연결
    logger.info("📱 [1단계] 모바일 클라이언트 연결 중...")
    mobile = MobileClient(socketio_url)
    if not await mobile.connect():
        logger.error("❌ 모바일 클라이언트 연결 실패!")
        return False
    
    await asyncio.sleep(1)
    
    # 2. 라즈베리파이 클라이언트 연결
    logger.info("\n🔌 [2단계] 라즈베리파이 클라이언트 연결 중...")
    raspi = RaspiClient(socketio_url)
    if not await raspi.connect():
        logger.error("❌ 라즈베리파이 클라이언트 연결 실패!")
        await mobile.disconnect()
        return False
    
    await asyncio.sleep(1)
    
    # 3. 버퍼링 STT 처리
    logger.info("\n🎤 [3단계] 버퍼링 STT 처리 시작...")
    try:
        from stt.gcp_stt_buffered import GcpBufferedStt
        from tests.test_stt_with_audio_file import AudioFileStream
        
        audio_stream = AudioFileStream(buffered_audio_file)
        audio_stream.start()
        
        buffered_stt = GcpBufferedStt()
        
        async def broadcaster(msg):
            if msg.get("type") == "final":
                await raspi.sio.emit("stt_result", msg)
                logger.info(f"📤 [라즈베리파이] 버퍼링 STT 전송: {msg.get('text', '')[:50]}...")
        
        stt_task = asyncio.create_task(buffered_stt.run(audio_stream, broadcaster))
        await stt_task
        
        audio_stream.stop()
        
    except Exception as e:
        logger.error(f"❌ 버퍼링 STT 처리 실패: {e}")
        import traceback
        traceback.print_exc()
        await raspi.disconnect()
        await mobile.disconnect()
        return False
    
    # 4. Intent 결과 수신 대기
    logger.info("\n⏳ [4단계] Intent 분류 대기 중...")
    for i in range(10):
        await asyncio.sleep(1)
        if mobile.intent_result_received:
            logger.info(f"✅ Intent 결과 수신 완료! ({i+1}초 소요)")
            break
    
    if not mobile.intent_result_received:
        logger.error("❌ Intent 결과 수신 타임아웃")
        await raspi.disconnect()
        await mobile.disconnect()
        return False
    
    if mobile.intent_result.get("intent") != "OPERATOR":
        logger.warning(f"⚠️ Intent가 OPERATOR가 아닙니다: {mobile.intent_result.get('intent')}")
    
    # 5. WebRTC 연결 요청 테스트
    logger.info("\n📞 [5단계] WebRTC 연결 요청 테스트...")
    try:
        import requests
        
        webrtc_url = f"{spring_url}/webrtc/request"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "receiverAccountId": 0  # TODO: 실제 수신자 계정 ID로 변경
        }
        
        response = requests.post(webrtc_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200 or response.status_code == 202:
            logger.info(f"✅ WebRTC 연결 요청 성공: {response.status_code}")
            logger.info(f"   응답: {response.text[:200]}...")
        else:
            logger.warning(f"⚠️ WebRTC 연결 요청 응답: {response.status_code}")
            logger.warning(f"   응답: {response.text[:200]}...")
    
    except Exception as e:
        logger.error(f"❌ WebRTC 연결 요청 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. 결과 요약
    logger.info("\n" + "="*70)
    logger.info("📊 테스트 결과 요약")
    logger.info("="*70)
    logger.info(f"✅ Intent 결과 수신: {mobile.intent_result_received}")
    if mobile.intent_result:
        logger.info(f"   Intent: {mobile.intent_result.get('intent')}")
        logger.info(f"   신뢰도: {mobile.intent_result.get('confidence', 0):.2f}")
    logger.info("="*70 + "\n")
    
    # 7. 정리
    logger.info("🧹 [6단계] 연결 정리 중...")
    await raspi.disconnect()
    await mobile.disconnect()
    
    success = mobile.intent_result_received and mobile.intent_result.get("intent") == "OPERATOR"
    
    if success:
        logger.info("\n✅ OPERATOR 분기 플로우 테스트 성공!")
    else:
        logger.error("\n❌ OPERATOR 분기 플로우 테스트 실패!")
    
    return success


async def main():
    parser = argparse.ArgumentParser(description="음성 파일 기반 전체 플로우 테스트")
    parser.add_argument("--buffered-audio", type=str, required=True, help="버퍼링 STT용 음성 파일 경로")
    parser.add_argument("--streaming-audio", type=str, help="Streaming STT용 음성 파일 경로 (AI_SUPPORTER 테스트용)")
    parser.add_argument("--socketio-url", type=str, default="http://localhost:5000", help="Socket.IO 서버 URL")
    parser.add_argument("--fastapi-url", type=str, default="http://localhost:8000", help="FastAPI 서버 URL")
    parser.add_argument("--spring-url", type=str, help="Spring 서버 URL (OPERATOR 테스트용)")
    parser.add_argument("--access-token", type=str, help="액세스 토큰 (OPERATOR 테스트용)")
    parser.add_argument("--test-type", type=str, choices=["ai_supporter", "operator"], required=True,
                       help="테스트 타입: ai_supporter 또는 operator")
    
    args = parser.parse_args()
    
    if args.test_type == "ai_supporter":
        if not args.streaming_audio:
            logger.error("❌ AI_SUPPORTER 테스트에는 --streaming-audio가 필요합니다.")
            return
        
        success = await test_ai_supporter_flow(
            buffered_audio_file=args.buffered_audio,
            streaming_audio_file=args.streaming_audio,
            socketio_url=args.socketio_url,
            fastapi_url=args.fastapi_url
        )
    else:  # operator
        if not args.spring_url or not args.access_token:
            logger.error("❌ OPERATOR 테스트에는 --spring-url과 --access-token이 필요합니다.")
            return
        
        success = await test_operator_flow(
            buffered_audio_file=args.buffered_audio,
            socketio_url=args.socketio_url,
            fastapi_url=args.fastapi_url,
            spring_url=args.spring_url,
            access_token=args.access_token
        )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

