"""
GCP STT 스트리밍 방식
실시간으로 음성을 인식하며, 대화형 시나리오에 적합합니다.
스트리밍 모드에서는 FastAPI 서버로 WebSocket을 통해 전송합니다.
"""
import time
import asyncio
from google.cloud import speech
from config import settings
from .websocket_client import FastApiWebSocketClient

class GcpStreamingStt:
    def __init__(self):
        self.language = settings.LANGUAGE
        self.rate = settings.RATE
        self.client = speech.SpeechClient()
        self._stop = False
        self.silence_timeout = settings.SILENCE_TIMEOUT_SEC if hasattr(settings, 'SILENCE_TIMEOUT_SEC') else 3.0
        self.ws_client = FastApiWebSocketClient()
        self.connected = False

    async def run(self, mic, broadcaster=None):
        """
        마이크에서 실시간 스트리밍으로 음성을 인식하고 FastAPI 서버로 WebSocket 전송합니다.
        
        Args:
            mic: MicStream 인스턴스
            broadcaster: 결과를 전송할 함수 (사용하지 않음, 호환성을 위해 유지)
        """
        # FastAPI 서버와 WebSocket 연결
        self.connected = await self.ws_client.connect()
        if not self.connected:
            print("❌ FastAPI 서버 WebSocket 연결 실패")
            return

        # 응답 수신 태스크 시작
        response_task = None
        try:
            async def handle_response(response):
                """FastAPI 서버 응답 처리"""
                resp_type = response.get("type", "")
                if resp_type == "clarify":
                    print(f"💡 Clarify 요청: {response.get('text', '')}")
                elif resp_type == "answer":
                    print(f"✅ 최종 답변: {response.get('text', '')}")
                elif resp_type == "session_end":
                    # 서비스 종료 신호
                    print("🔚 서비스 종료 신호 수신")
                    self._stop = True
                elif resp_type == "error":
                    print(f"❌ 오류: {response.get('text', '')}")

            # 응답 수신 태스크 시작
            response_task = asyncio.create_task(
                self.ws_client.listen_responses(handle_response)
            )

            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.rate,
                language_code=self.language,
                enable_automatic_punctuation=True,
            )
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,  # 중간 결과도 전송
            )

            last_voice_ts = time.time()
            self._stop = False

            loop = asyncio.get_running_loop()
            results_queue: asyncio.Queue = asyncio.Queue()

            def gen():
                """오디오 청크 생성기"""
                nonlocal last_voice_ts
                while not self._stop:
                    chunk = mic.read()
                    if chunk is None:
                        break
                    # 음성이 감지되면 타임스탬프 업데이트
                    if len(chunk) > 0:
                        last_voice_ts = time.time()
                    yield speech.StreamingRecognizeRequest(audio_content=chunk)

            def blocking_stream():
                """블로킹 스트리밍 인식"""
                try:
                    responses = self.client.streaming_recognize(streaming_config, gen())
                    for response in responses:
                        # 서비스 종료 신호 확인
                        if self._stop:
                            break
                            
                        for result in response.results:
                            txt = result.alternatives[0].transcript
                            confidence = result.alternatives[0].confidence if hasattr(result.alternatives[0], 'confidence') else None
                            msg_type = "final" if result.is_final else "interim"
                            
                            # 중간 결과 또는 최종 결과 전송
                            asyncio.run_coroutine_threadsafe(
                                results_queue.put({
                                    "type": msg_type,
                                    "text": txt,
                                    "confidence": confidence
                                }),
                                loop
                            )

                        # 침묵 타임아웃은 무시 (서비스 종료 신호까지 계속 대기)
                        # 마이크는 계속 켜져있고 다음 입력을 기다림
                except Exception as e:
                    asyncio.run_coroutine_threadsafe(
                        results_queue.put({"type": "error", "text": str(e)}),
                        loop
                    )
                finally:
                    # 종료 신호 전송
                    asyncio.run_coroutine_threadsafe(results_queue.put(None), loop)

            # 스트리밍 인식 시작 (별도 스레드에서 실행)
            await loop.run_in_executor(None, blocking_stream)

            # 결과 수신 및 WebSocket 전송
            while True:
                # 서비스 종료 신호 확인
                if self._stop:
                    print("🔚 서비스 종료: 스트리밍 세션 종료")
                    break
                    
                msg = await results_queue.get()
                if msg is None:
                    break
                
                msg_type = msg.get("type")
                txt = msg.get("text", "")
                confidence = msg.get("confidence")
                
                if msg_type in ("final", "interim"):
                    # 최종 결과만 FastAPI 서버로 WebSocket 전송
                    if msg_type == "final":
                        print(f"📝 STT 최종 결과: {txt}")
                        # WebSocket으로 전송
                        success = await self.ws_client.send_text(txt)
                        if not success:
                            print("⚠️ WebSocket 전송 실패, 재연결 시도...")
                            self.connected = await self.ws_client.connect()
                            if self.connected:
                                await self.ws_client.send_text(txt)
                    
                    # 로그 출력 (interim 결과도 표시)
                    if msg_type == "interim":
                        print(f"🔄 STT 중간 결과: {txt}")
                        
                elif msg_type in ("info", "error"):
                    print(f"⚠️ {msg_type}: {txt}")
                    # 서비스 종료는 FastAPI 서버의 session_end 메시지로만 처리
                    # 침묵 타임아웃이나 기타 정보는 무시하고 계속 대기

        finally:
            # 응답 수신 태스크 취소
            if response_task:
                response_task.cancel()
                try:
                    await response_task
                except asyncio.CancelledError:
                    pass
            
            # WebSocket 연결 종료
            await self.ws_client.disconnect()
            self.connected = False
            # 세션 초기화 (다음 대화를 위해)
            self.ws_client.reset_session()

    def stop(self):
        """스트리밍 중지"""
        self._stop = True
