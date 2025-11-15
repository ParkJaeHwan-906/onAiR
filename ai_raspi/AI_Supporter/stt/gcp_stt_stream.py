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
import numpy as np

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
        self.silence_timeout = settings.SILENCE_TIMEOUT_SEC if hasattr(settings, 'SILENCE_TIMEOUT_SEC') else 0.5
        self.socketio_client = socketio_client
        self.session_id = None  # Clarify 세션 ID
        self.stop_sessions = set()  # 종료할 세션 ID 집합
        # 타이머 기반 침묵 감지용 변수
        self.last_activity_time = None  # 마지막 STT 결과 수신 시간
        self.force_final_sent = False  # 강제 final 이벤트 전송 플래그
        self.monitor_task = None  # 침묵 모니터링 태스크
        self.last_interim_text = ""  # 마지막 interim 결과 저장 (침묵 타임아웃 시 사용)

    async def run(self, mic, broadcaster=None, session_id: str = None):
        """
        마이크에서 실시간 스트리밍으로 음성을 인식하고 Socket.IO 서버로 전송합니다.
        
        Args:
            mic: MicStream 인스턴스
            broadcaster: 결과를 전송할 함수 (Python 3.10에서 브리지 서버로 전송용)
            session_id: Clarify 세션 ID (선택사항, 있으면 Streaming STT로 처리됨)
        """
        # socketio_client 또는 broadcaster 중 하나는 있어야 함
        if not self.socketio_client and not broadcaster:
            print("❌ Socket.IO 클라이언트 또는 broadcaster가 설정되지 않았습니다.")
            return
        
        # socketio_client가 있으면 연결 상태 확인
        if self.socketio_client and not self.socketio_client.is_connected():
            print("❌ Socket.IO 서버에 연결되어 있지 않습니다.")
            return
        
        # 세션 ID 설정
        self.session_id = session_id or str(uuid.uuid4())
        print(f"🔗 Streaming STT 세션 시작: session_id={self.session_id}")
        print(f"⏱️ 침묵 타임아웃: {self.silence_timeout}초")

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
            self.force_final_sent = False
            self.last_activity_time = time.time()  # 초기화
            self.last_interim_text = ""  # 초기화

            loop = asyncio.get_running_loop()
            results_queue: asyncio.Queue = asyncio.Queue()
            
            # 침묵 모니터링 태스크 시작
            self.monitor_task = asyncio.create_task(
                self._monitor_silence(results_queue, loop)
            )

            def gen():
                """오디오 청크 생성기"""
                while not self._stop:
                    chunk = mic.read()
                    if chunk is None:
                        break
                    if isinstance(chunk, np.ndarray):
                        chunk = chunk.tobytes()  # numpy → bytes 변환
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
                            
                            # STT 결과 수신 시 활동 시간 갱신 (침묵 타이머 리셋)
                            asyncio.run_coroutine_threadsafe(
                                self._update_activity_time(),
                                loop
                            )
                            
                            # 중간 결과 또는 최종 결과 전송
                            asyncio.run_coroutine_threadsafe(
                                results_queue.put({
                                    "type": msg_type,
                                    "text": txt,
                                    "confidence": confidence
                                }),
                                loop
                            )
                            
                            # GCP STT가 final을 반환하면 강제 final 플래그 설정
                            if result.is_final:
                                asyncio.run_coroutine_threadsafe(
                                    self._set_force_final(),
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

            # Clarify 루프를 위해 여러 번 스트림 실행 (stop 신호를 받을 때까지)
            while not self._stop:
                # 종료 신호 확인
                if self.session_id and self.session_id in self.stop_sessions:
                    print(f"🛑 Streaming STT 종료 신호 수신: session_id={self.session_id}")
                    self.stop_sessions.remove(self.session_id)
                    self._stop = True
                    break
                
                # 상태 리셋 (새로운 스트림 시작 전)
                self.force_final_sent = False
                self.last_activity_time = time.time()
                self.last_interim_text = ""
                
                # 침묵 모니터링 태스크 재시작
                if self.monitor_task:
                    self.monitor_task.cancel()
                    try:
                        await self.monitor_task
                    except asyncio.CancelledError:
                        pass
                self.monitor_task = asyncio.create_task(
                    self._monitor_silence(results_queue, loop)
                )
                
                # 스트리밍 인식 시작 (별도 스레드에서 실행)
                await loop.run_in_executor(None, blocking_stream)

                # 결과 수신 및 Socket.IO 전송 (Clarify 루프를 위해 계속 실행)
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
                        # blocking_stream이 종료되었지만, Clarify 루프를 위해 재시작
                        print("🔄 Streaming STT 스트림 종료 → 다음 입력 대기 (재시작)")
                        # 상위 루프로 돌아가서 새로운 스트림 시작
                        break
                    
                    msg_type = msg.get("type")
                    txt = msg.get("text", "")
                    confidence = msg.get("confidence")
                    
                    if msg_type in ("final", "interim"):
                        # 최종 결과만 전송
                        if msg_type == "final":
                            print("=" * 60)
                            print(f"📝 [라즈베리파이] STT 최종 결과 수신 (한 문장 완성)")
                            print(f"   Session ID: {self.session_id}")
                            print(f"   텍스트: {txt}")
                            print(f"   신뢰도: {confidence}")
                            print("=" * 60)
                            self.force_final_sent = True  # final 수신 시 플래그 설정
                            
                            # 전송 방식 선택: socketio_client 우선, 없으면 broadcaster 사용
                            if self.socketio_client:
                                # Socket.IO 클라이언트로 직접 전송 (Python 3.13에서 사용)
                                print("=" * 60)
                                print(f"📤 [라즈베리파이] FastAPI로 STT 결과 전송 시작")
                                print(f"   Session ID: {self.session_id}")
                                print(f"   텍스트: {txt[:50]}...")
                                print("=" * 60)
                                success = await self.socketio_client.emit_streaming_stt(
                                    text=txt,
                                    msg_type="final",
                                    confidence=confidence,
                                    session_id=self.session_id
                                )
                                if success:
                                    print("=" * 60)
                                    print(f"✅ [라즈베리파이] FastAPI로 STT 결과 전송 완료")
                                    print("=" * 60)
                                else:
                                    print("=" * 60)
                                    print(f"❌ [라즈베리파이] FastAPI로 STT 결과 전송 실패")
                                    print("=" * 60)
                            elif broadcaster:
                                # Broadcaster를 통해 브리지 서버로 전송 (Python 3.10에서 사용)
                                print("=" * 60)
                                print(f"📤 [라즈베리파이] FastAPI로 STT 결과 전송 시작 (브리지 서버 경유)")
                                print(f"   Session ID: {self.session_id}")
                                print(f"   텍스트: {txt[:50]}...")
                                print("=" * 60)
                                stt_result = {
                                    "type": "final",
                                    "text": txt,
                                    "confidence": confidence,
                                    "session_id": self.session_id
                                }
                                await broadcaster(stt_result)
                                print("=" * 60)
                                print(f"✅ [라즈베리파이] FastAPI로 STT 결과 전송 완료 (브리지 서버 경유)")
                                print("=" * 60)
                            
                            # final 전송 후 상위 루프로 돌아가서 새로운 스트림 시작
                            print("=" * 60)
                            print(f"🔄 [라즈베리파이] STT 결과 전송 완료 → 다음 입력 대기 중...")
                            print(f"   💡 사용자가 다음 질문을 말할 때까지 대기")
                            print("=" * 60)
                            break
                        
                        # 로그 출력 (interim 결과도 표시)
                        if msg_type == "interim":
                            print(f"🔄 STT 중간 결과: {txt}")
                            self.last_interim_text = txt  # 마지막 interim 결과 저장 (침묵 타임아웃 시 사용)
                            
                    elif msg_type in ("info", "error"):
                        print(f"⚠️ {msg_type}: {txt}")
                    elif msg_type == "silence_timeout":
                        # 침묵 타임아웃으로 인한 강제 final
                        print("=" * 60)
                        print(f"🕓 [라즈베리파이] 침묵 타임아웃 감지 → 발화 종료 처리 (한 문장 완성)")
                        print(f"   Session ID: {self.session_id}")
                        print("=" * 60)
                        # 마지막 interim 결과 사용 (없으면 빈 문자열)
                        final_text = txt if txt else self.last_interim_text
                        print(f"   사용할 텍스트: '{final_text}'")
                        self.force_final_sent = True
                        
                        # 전송 방식 선택: socketio_client 우선, 없으면 broadcaster 사용
                        success = False
                        if self.socketio_client:
                            # Socket.IO 클라이언트로 직접 전송 (Python 3.13에서 사용)
                            print("=" * 60)
                            print(f"📤 [라즈베리파이] FastAPI로 STT 결과 전송 시작 (침묵 타임아웃)")
                            print(f"   Session ID: {self.session_id}")
                            print(f"   텍스트: {final_text[:50]}...")
                            print("=" * 60)
                            success = await self.socketio_client.emit_streaming_stt(
                                text=final_text,
                                msg_type="final",
                                confidence=confidence,
                                session_id=self.session_id
                            )
                            if success:
                                print("=" * 60)
                                print(f"✅ [라즈베리파이] FastAPI로 STT 결과 전송 완료 (침묵 타임아웃)")
                                print("=" * 60)
                            else:
                                print("=" * 60)
                                print(f"❌ [라즈베리파이] FastAPI로 STT 결과 전송 실패 (침묵 타임아웃)")
                                print("=" * 60)
                        elif broadcaster:
                            # Broadcaster를 통해 브리지 서버로 전송 (Python 3.10에서 사용)
                            print("=" * 60)
                            print(f"📤 [라즈베리파이] FastAPI로 STT 결과 전송 시작 (침묵 타임아웃, 브리지 서버 경유)")
                            print(f"   Session ID: {self.session_id}")
                            print(f"   텍스트: {final_text[:50]}...")
                            print("=" * 60)
                            stt_result = {
                                "type": "final",
                                "text": final_text,
                                "confidence": confidence,
                                "session_id": self.session_id
                            }
                            await broadcaster(stt_result)
                            print("=" * 60)
                            print(f"✅ [라즈베리파이] FastAPI로 STT 결과 전송 완료 (침묵 타임아웃, 브리지 서버 경유)")
                            print("=" * 60)
                            success = True
                        
                        if not success:
                            print("=" * 60)
                            print(f"❌ [라즈베리파이] STT 결과 전송 실패")
                            print("=" * 60)
                        # 상위 루프로 돌아가서 새로운 스트림 시작
                        print("=" * 60)
                        print(f"🔄 [라즈베리파이] STT 결과 전송 완료 → 다음 입력 대기 중...")
                        print(f"   💡 사용자가 다음 질문을 말할 때까지 대기")
                        print("=" * 60)
                        break

        finally:
            # 침묵 모니터링 태스크 취소
            if self.monitor_task:
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
            
            # 세션 ID 초기화 (다음 대화를 위해)
            self.session_id = None
            self.last_activity_time = None
            self.force_final_sent = False
            self.last_interim_text = ""
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
    
    async def _update_activity_time(self):
        """STT 결과 수신 시 활동 시간 갱신 (침묵 타이머 리셋)"""
        self.last_activity_time = time.time()
    
    async def _set_force_final(self):
        """GCP STT가 final을 반환했을 때 플래그 설정"""
        self.force_final_sent = True
    
    async def _monitor_silence(self, results_queue: asyncio.Queue, loop):
        """
        침묵 감지 모니터링: 일정 시간동안 STT 결과가 없으면 종료 처리
        
        Args:
            results_queue: STT 결과 큐
            loop: 이벤트 루프
        """
        check_interval = 0.2  # 200ms마다 확인
        
        while not self.force_final_sent and not self._stop:
            try:
                await asyncio.sleep(check_interval)
                
                # 세션 종료 신호 확인
                if self.session_id and self.session_id in self.stop_sessions:
                    break
                
                if self._stop:
                    break
                
                # 활동 시간 확인
                if self.last_activity_time is None:
                    continue
                
                elapsed = time.time() - self.last_activity_time
                
                # 침묵 타임아웃 발생 시 강제 final 이벤트 발생
                if elapsed >= self.silence_timeout:
                    print(f"🕓 침묵 {elapsed:.1f}초 경과 (타임아웃: {self.silence_timeout}초) → 발화 종료 처리")
                    
                    # 강제 final 이벤트를 큐에 추가
                    # 마지막 interim 결과는 메인 루프에서 self.last_interim_text 사용
                    asyncio.run_coroutine_threadsafe(
                        results_queue.put({
                            "type": "silence_timeout",
                            "text": "",  # 마지막 interim 결과는 메인 루프에서 사용
                            "confidence": None,
                            "reason": "silence_timeout"
                        }),
                        loop
                    )
                    
                    self.force_final_sent = True
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ 침묵 모니터링 오류: {e}")
                break
