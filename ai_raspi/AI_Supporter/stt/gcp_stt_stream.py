"""
GCP STT 스트리밍 방식
실시간으로 음성을 인식하며, 대화형 시나리오에 적합합니다.
스트리밍 모드에서는 Socket.IO를 통해 전송합니다.
"""
import time
import asyncio
import uuid
from google.cloud import speech
from config import settings

class GcpStreamingStt:
    def __init__(self, socketio_client=None):
        """
        Args:
            socketio_client: SocketIOClient 인스턴스 (필수)
        """
        self.language = settings.LANGUAGE
        self.rate = settings.RATE
        self.client = speech.SpeechClient()
        self._stop = False
        self.silence_timeout = settings.SILENCE_TIMEOUT_SEC if hasattr(settings, 'SILENCE_TIMEOUT_SEC') else 3.0
        self.socketio_client = socketio_client
        self.session_id = None  # Clarify 세션 ID
        self.stop_sessions = set()  # 종료할 세션 ID 집합

    async def run(self, mic, broadcaster=None, session_id: str = None):
        """
        마이크에서 실시간 스트리밍으로 음성을 인식하고 Socket.IO 서버로 전송합니다.
        
        Args:
            mic: MicStream 인스턴스
            broadcaster: 결과를 전송할 함수 (사용하지 않음, 호환성을 위해 유지)
            session_id: Clarify 세션 ID (선택사항, 있으면 Streaming STT로 처리됨)
        """
        if not self.socketio_client:
            print("❌ Socket.IO 클라이언트가 설정되지 않았습니다.")
            return
        
        if not self.socketio_client.is_connected():
            print("❌ Socket.IO 서버에 연결되어 있지 않습니다.")
            return
        
        # 세션 ID 설정
        self.session_id = session_id or str(uuid.uuid4())
        print(f"🔗 Streaming STT 세션 시작: session_id={self.session_id}")

        try:
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

            # 결과 수신 및 Socket.IO 전송
            while True:
                # 🆕 종료 신호 확인
                if self.session_id and self.session_id in self.stop_sessions:
                    print(f"🛑 Streaming STT 종료 신호 수신: session_id={self.session_id}")
                    self.stop_sessions.remove(self.session_id)
                    self._stop = True
                    break
                
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
                    # 최종 결과만 Socket.IO로 전송
                    if msg_type == "final":
                        print(f"📝 STT 최종 결과: {txt}")
                        # Socket.IO로 전송 (session_id 포함)
                        success = await self.socketio_client.emit_streaming_stt(
                            text=txt,
                            msg_type="final",
                            confidence=confidence,
                            session_id=self.session_id
                        )
                        if not success:
                            print("⚠️ Socket.IO 전송 실패")
                    
                    # 로그 출력 (interim 결과도 표시)
                    if msg_type == "interim":
                        print(f"🔄 STT 중간 결과: {txt}")
                        
                elif msg_type in ("info", "error"):
                    print(f"⚠️ {msg_type}: {txt}")

        finally:
            # 세션 ID 초기화 (다음 대화를 위해)
            self.session_id = None
            print("🟢 Streaming STT 세션 종료")

    def stop(self):
        """스트리밍 중지"""
        self._stop = True
    
    def stop_session(self, session_id: str):
        """특정 세션의 스트리밍 중지"""
        self.stop_sessions.add(session_id)
        if self.session_id == session_id:
            self._stop = True
    
    def set_session_id(self, session_id: str):
        """세션 ID 설정"""
        self.session_id = session_id
