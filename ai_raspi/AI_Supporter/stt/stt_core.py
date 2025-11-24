import threading
import asyncio
import time
import re
import logging
import numpy as np
from jamo import h2j, j2hcj

from stt.mic_stream import MicStream
from stt.gcp_stt_buffered import GcpBufferedStt
from stt.wakeword_hook import init_wakeword_detector

logger = logging.getLogger(__name__)

class STTCore:
    def __init__(self, manager):
        """
        manager: AudioModeManager 인스턴스
        """
        self.manager = manager
        self.mic = manager.mic
        self.wakeword_detector = init_wakeword_detector()
        self.buffered_stt = GcpBufferedStt()

        # wakeword 오디오 송출이 완료되었는지 
        self.wakeword_audio_done = threading.Event()
        self.operator_accept = threading.Event()
        
        # wakeword 감지 무시 플래그 (서비스 진행 중에는 True)
        self.ignore_wakeword = False

        # Threshold
        self.WAKEWORD_LCS_THRESHOLD_ENG = 0.60
        self.WAKEWORD_LCS_THRESHOLD_KOR = 0.60

    # ---------------------------------
    # 유틸 함수
    # ---------------------------------
    def lcs_ratio(self, a, b):
        import difflib
        ratios = []
        for item in b:
            s = difflib.SequenceMatcher(None, a, item)
            ratios.append(s.ratio())
        return max(ratios)

    def regx_text(self, text):
        return re.sub(r'[^A-Za-z가-힣]', '', text)

    def to_jamo(self, text: str) -> str:
        try:
            return j2hcj(h2j(text))
        except:
            return text

    def compute_similarity(self, text, keyword="온에어"):
        cleaned = self.regx_text(text)

        # 영어
        if all(ord(c) < 128 for c in cleaned):
            return self.lcs_ratio(cleaned.lower(), ["onair"]), "ENG"

        # 한국어
        cleaned_jamo = self.to_jamo(cleaned)
        # keyword_jamo = self.to_jamo(keyword)
        # Sample 증가
        keyword_jamo = [self.to_jamo("온에어"), self.to_jamo("오네요"), self.to_jamo("오내요")
                        , self.to_jamo("보네요"), self.to_jamo("보내요")]
        return self.lcs_ratio(cleaned_jamo, keyword_jamo), "KOR"

    def reset_to_initial_state(self):
        """
        서비스 메인 루프 종료 후 초기 상태로 복귀
        - Wakeword 감지기 재개
        - 마이크 활성화
        - 모든 플래그 초기화
        """
        logger.info("=" * 60)
        logger.info("🔄 초기 상태로 복귀 시작")
        logger.info("=" * 60)
        
        try:
            # 1. RTC 모드 종료 (혹시 실행 중이었다면)
            if self.manager.is_rtc_running:
                logger.info("📡 RTC 모드 종료 중...")
                self.manager.switch_to_stt()
                logger.info("✅ RTC 모드 종료 완료")
            
            # 2. 마이크 상태 확인 및 활성화
            if not self.mic.is_active():
                logger.info("🎤 마이크 활성화 중...")
                if self.mic.stream is None:
                    self.mic.acquire()
                else:
                    self.mic.resume()
                logger.info("✅ 마이크 활성화 완료")
            
            # 3. Wakeword 감지기 재개
            if not self.wakeword_detector.is_running:
                logger.info("🔊 Wakeword 감지기 시작 중...")
                self.wakeword_detector.start()
            elif self.wakeword_detector.is_paused:
                logger.info("🔊 Wakeword 감지기 재개 중...")
                self.wakeword_detector.resume()
            
            # 4. 마이크에 wakeword 콜백 재등록
            self.mic.enable_wakeword_callback(self.wakeword_detector.process_audio_chunk)
            
            # 5. wakeword 감지 무시 플래그 해제
            self.ignore_wakeword = False
            
            logger.info("=" * 60)
            logger.info("✅ 초기 상태 복귀 완료 - Wakeword 감지 대기 중...")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 초기 상태 복귀 중 오류: {e}")
            import traceback
            traceback.print_exc()

    # ---------------------------------
    # STT Worker (기존 run_stt_loop)
    # ---------------------------------
    def run(self):
        """
        STT Worker 스레드에서 실행될 메인 루프
        Manager를 활용해 STT/RTC 모드를 전환함
        """
        try:
            logger.info("=" * 60)
            logger.info("🎯 STT Core.run() 시작")
            logger.info(f"   스레드 ID: {threading.current_thread().ident}")
            logger.info(f"   스레드 이름: {threading.current_thread().name}")
            
            # Socket.IO 연결을 기다리지 않고 바로 시작
            # (Socket.IO 연결은 별도 스레드에서 처리되며, 이벤트 전송 시에만 연결 상태 확인)

            # Wakeword 감지기 시작 확인
            logger.info("🔍 Wakeword 감지기 상태 확인 중...")
            if self.wakeword_detector is None:
                logger.error("❌ Wakeword 감지기가 초기화되지 않았습니다.")
                return
            
            logger.info(f"   wakeword_detector: {self.wakeword_detector}")
            logger.info(f"   interpreter: {self.wakeword_detector.interpreter}")
            logger.info(f"   is_running: {self.wakeword_detector.is_running}")
            logger.info(f"   is_paused: {self.wakeword_detector.is_paused}")
            
            if self.wakeword_detector.interpreter is None:
                logger.error("❌ Wakeword 모델이 로드되지 않았습니다.")
                return
            
            # Wakeword 감지기가 실행 중인지 확인
            if not self.wakeword_detector.is_running:
                logger.warning("⚠️ Wakeword 감지기가 시작되지 않았습니다. 시작합니다...")
                self.wakeword_detector.start()
                logger.info(f"   시작 후 is_running: {self.wakeword_detector.is_running}")
            
            # Wakeword 감지기 재개 (pause 상태일 수 있음)
            if self.wakeword_detector.is_paused:
                logger.warning("⚠️ Wakeword 감지기가 일시 중지 상태입니다. 재개합니다...")
                self.wakeword_detector.resume()
                logger.info(f"   재개 후 is_paused: {self.wakeword_detector.is_paused}")

            # Wakeword callback 설치 (마이크 시작 전에 설정)
            logger.info("🔧 Wakeword 콜백 설정 중...")
            self.mic.set_wakeword_callback(self.wakeword_detector.process_audio_chunk)
            
            # 콜백이 제대로 설정되었는지 확인
            if self.mic.wakeword_callback is None:
                logger.error("❌ Wakeword 콜백이 설정되지 않았습니다.")
                return
            logger.info("✅ Wakeword 콜백 설정 완료")

            # Mic 시작 (acquire 사용 - release된 상태에서도 안전하게 재시작)
            # 초기 상태이거나 RTC 모드에서 STT 모드로 전환된 경우 모두 처리
            logger.info("🎤 마이크 시작 중...")
            try:
                # acquire()가 stream 상태를 확인하고 필요시 재시작함
                self.mic.acquire()
                logger.info("✅ 마이크 acquire() 완료")
            except Exception as e:
                logger.error(f"❌ 마이크 시작 실패: {e}")
                import traceback
                traceback.print_exc()
                return

            # 마이크가 활성 상태인지 확인
            logger.info("🔍 마이크 활성 상태 확인 중...")
            if not self.mic.is_active():
                logger.error("❌ 마이크가 활성 상태가 아닙니다.")
                logger.error(f"   stream: {self.mic.stream}")
                logger.error(f"   is_paused: {self.mic.is_paused}")
                if self.mic.stream:
                    logger.error(f"   stream.active: {self.mic.stream.active if hasattr(self.mic.stream, 'active') else 'N/A'}")
                return
            
            # 마이크 스트림이 실제로 시작되었는지 확인
            if self.mic.stream is None:
                logger.error("❌ 마이크 스트림이 None입니다.")
                return
            
            if not hasattr(self.mic.stream, 'active') or not self.mic.stream.active:
                logger.error("❌ 마이크 스트림이 활성화되지 않았습니다.")
                return

            logger.info("=" * 60)
            logger.info("✅ 마이크 스트림 활성화 완료 - Wakeword 감지 대기 중...")
            logger.info("=" * 60)

            while True:
                try:
                    """
                    계속해서 wakeword 가 들어올 때까지 대기
                    """
                    if not self.ignore_wakeword:
                        # Wakeword 감지기 상태 확인
                        if not self.wakeword_detector.is_running:
                            logger.warning("⚠️ Wakeword 감지기가 중지되었습니다. 재시작합니다...")
                            self.wakeword_detector.start()
                        
                        if self.wakeword_detector.is_paused:
                            self.wakeword_detector.resume()
                        
                        # 마이크 상태 확인
                        if not self.mic.is_active():
                            logger.warning("⚠️ 마이크가 비활성 상태입니다. 재개합니다...")
                            self.mic.resume()
                        
                        # wait_for_wakeword는 blocking이므로 timeout을 짧게 설정하여
                        # 루프 내에서 다른 상태 확인도 가능하도록 함
                        detected = self.wakeword_detector.wait_for_wakeword(timeout=1.0)
                        if not detected:
                            continue
                        
                        # 1단계: wakeword 감지 시점의 오디오 가져오기
                        logger.info("🎤 Wakeword 감지됨! 교차 검증을 위해 음성 데이터를 가져옵니다...")
                        raw_audio = self.wakeword_detector.get_recent_audio()
                        if not raw_audio:
                            logger.warning("⚠️ 음성 데이터가 None입니다")
                            continue
                        
                        # ---------------------------------------------------------------------
                        # 마이크 큐에 쌓인 오래된 오디오 제거 (이전 wakeword 감지의 잔여 데이터 방지)
                        # self.mic.flush_queue()
                        # logger.info("🧹 마이크 큐 비움 완료 (새로운 오디오 수집 준비)")
                        
                        # 2단계: wakeword 감지 후 추가로 오디오 수집 (최대 1.0초)
                        # 버퍼를 clear했으므로, 이후 들어오는 오디오는 wakeword 이후의 오디오
                        # additional_audio_chunks = []
                        # collect_duration = 1.0  # 추가로 1.0초 수집 (0.5초 → 1.0초로 증가)
                        # collect_samples = int(16000 * collect_duration)  # 16000 샘플
                        # collected_samples = 0
                        # start_collect_time = time.time()
                        
                        # logger.info(f"📥 Wakeword 감지 후 추가 오디오 수집 시작 (목표: {collect_duration}초)")
                        
                        # while collected_samples < collect_samples and (time.time() - start_collect_time) < collect_duration + 0.3:  # 타임아웃 1.3초
                        #     chunk = self.mic.read(timeout=0.1)
                        #     if chunk is not None:
                                # 16000Hz로 리샘플링된 오디오를 bytes로 변환
                                # if isinstance(chunk, np.ndarray):
                                #     chunk_bytes = chunk.astype(np.int16).tobytes()
                                # else:
                                #     chunk_bytes = chunk
                                # additional_audio_chunks.append(chunk_bytes)
                                # collected_samples += len(chunk_bytes) // 2  # 16bit = 2 bytes per sample
                        
                        # 3단계: 기존 오디오 + 추가 오디오 합치기
                        # if additional_audio_chunks:
                        #     additional_audio = b''.join(additional_audio_chunks)
                        #     raw_audio = raw_audio + additional_audio
                        #     logger.info(f"✅ 추가 오디오 수집 완료: {len(additional_audio)} bytes 추가 (총 {len(raw_audio)} bytes)")
                        # else:
                        #     logger.warning("⚠️ 추가 오디오 수집 실패 (타임아웃 또는 큐 비어있음)")
                        
                        # 오디오 품질 확인 (RMS 값으로 볼륨 체크)
                        # audio_array = np.frombuffer(raw_audio, dtype=np.int16)
                        # rms = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2))
                        # max_abs = np.max(np.abs(audio_array))
                        # logger.info(f"🔊 오디오 품질: RMS={rms:.1f}, 최대값={max_abs}")
                        
                        # 오디오 길이 확인 (최소 0.5초 = 16000Hz * 0.5 * 2 bytes = 16000 bytes)
                        # GCP STT는 최소 0.5초 이상의 오디오가 필요하지만, 실제로는 1.5초 이상이 권장됨
                        # MIN_AUDIO_LENGTH = int(16000 * 0.5 * 2)  # 0.5초 최소
                        # RECOMMENDED_AUDIO_LENGTH = int(16000 * 1.5 * 2)  # 1.5초 권장 (1.0초 → 1.5초로 증가)
                        # audio_length = len(raw_audio)
                        # audio_duration = audio_length / 2 / 16000  # bytes -> samples -> seconds
                        
                        # logger.info(f"📊 최종 오디오 정보: 길이={audio_length} bytes, 지속시간={audio_duration:.2f}초")
                        
                        # if audio_length < MIN_AUDIO_LENGTH:
                        #     logger.warning(f"⚠️ 음성 데이터가 너무 짧음 (길이: {audio_length} bytes, 최소: {MIN_AUDIO_LENGTH} bytes, 지속시간: {audio_duration:.2f}초)")
                        #     continue
                        
                        # if audio_length < RECOMMENDED_AUDIO_LENGTH:
                        #     logger.warning(f"⚠️ 음성 데이터가 권장 길이보다 짧음 (길이: {audio_length} bytes, 권장: {RECOMMENDED_AUDIO_LENGTH} bytes, 지속시간: {audio_duration:.2f}초) - STT 실패 가능성 있음")
                        # ---------------------------------------------------------------------
                        stt_text = None
                        stt_error = None
                        # STT 로 교차 검증
                        async def stt_verify():
                            nonlocal stt_text, stt_error

                            async def capture(msg):
                                nonlocal stt_text, stt_error
                                msg_type = msg.get("type")
                                logger.info(f"📨 STT 콜백 수신: type={msg_type}, text={msg.get('text', 'N/A')[:50]}")
                                
                                if msg_type == "final":
                                    stt_text = msg.get("text")
                                    logger.info(f"✅ STT 최종 결과: {stt_text}")
                                elif msg_type == "error":
                                    stt_error = msg.get("text", "알 수 없는 오류")
                                    logger.error(f"❌ STT 오류: {stt_error}")
                                else:
                                    logger.warning(f"⚠️ STT 알 수 없는 타입: {msg_type}")

                            logger.info(f"🎙️ GCP STT 호출 시작 (오디오 길이: {len(raw_audio)} bytes)")
                            try:
                                await self.buffered_stt.transcribe_bytes(raw_audio, capture)
                                logger.info("✅ GCP STT 호출 완료")
                            except Exception as e:
                                logger.error(f"❌ GCP STT 호출 중 예외 발생: {e}")
                                import traceback
                                traceback.print_exc()
                                stt_error = str(e)

                        # loop이 None이면 새로 생성하여 사용
                        loop = self.manager.socketio_client.loop
                        if loop is None:
                            # loop이 아직 설정되지 않았으면 새로 생성
                            logger.warning("⚠️ Socket.IO loop이 None입니다. 새 이벤트 루프 생성")
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            # 새 루프에서 직접 실행
                            loop.run_until_complete(stt_verify())
                        else:
                            # loop이 있으면 thread-safe로 실행
                            logger.info(f"🔄 Socket.IO loop 사용 (스레드 안전 실행)")
                            future = asyncio.run_coroutine_threadsafe(stt_verify(), loop)
                            try:
                                future.result(timeout=15.0)  # 타임아웃 15초로 증가
                            except Exception as e:
                                logger.error(f"❌ STT 실행 타임아웃 또는 오류: {e}")
                                stt_error = str(e)

                        if stt_error:
                            logger.warning(f"⚠️ STT 오류로 인해 스킵: {stt_error}")
                            continue
                        
                        if not stt_text:
                            logger.warning("⚠️ STT 결과 없음 (stt_text가 None이거나 빈 값)")
                            continue
                        logger.info(f"📝 STT 결과: {stt_text}")
                        similarity, lang = self.compute_similarity(stt_text)
                        threshold = (self.WAKEWORD_LCS_THRESHOLD_ENG 
                                     if lang == "ENG" 
                                     else self.WAKEWORD_LCS_THRESHOLD_KOR)
                        logger.info(f"📊 유사도: {similarity:.3f}, 언어: {lang}, 임계값: {threshold}")
                        if similarity < threshold:
                            logger.warning(f"⚠️ 유사도가 임계값 미만 ({similarity:.3f} < {threshold})")
                            # 유사도 검증 실패 시 마이크 큐 비우기 (다음 wakeword 감지를 위해)
                            self.mic.flush_queue()
                            logger.info("🧹 유사도 검증 실패로 인해 마이크 큐 비움 (다음 wakeword 감지 준비)")
                            continue
                        logger.info("✅ Wakeword 검증 성공!")
                        # Wakeword 성공
                        self.manager.on_wakeword_detected()
                        self.manager.wakeword_count += 1
                        
                        # Wakeword 오디오 FastAPI 전송 완료 대기
                        self.wakeword_audio_done.clear()
                        self.wakeword_audio_done.wait()
                        time.sleep(3)     
                    
                        # 현재 단계에서는 wakeword 감지 중지
                        self.ignore_wakeword = True 
                        self.wakeword_detector.pause() 

                        # 홀수 → STT
                        if self.manager.wakeword_count % 2 == 1:
                            # 시연 시에는, AI 서포터로 무조건 
                            self.manager.switch_to_stt()
                            # AI 서포터 전송
                            self.manager.on_ai_supporter()
                            time.sleep(1.0)
                        else:
                            # 오퍼레이터 통신 전송
                            self.manager.on_connect_operator()
                            # 수락을 했을 때
                            self.operator_accept.clear()
                            self.operator_accept.wait()
                            # 시연 시에는, 오퍼레이터 통신으로 무조건
                            self.manager.switch_to_rtc()
                            time.sleep(1.0)

                    if self.manager.is_rtc_running:
                        self.wakeword_detector.pause()
                        time.sleep(0.1)
                        continue

                    # RTC 모드가 종료되면 초기 상태로 복귀
                    self.ignore_wakeword = False
                    self.wakeword_detector.resume()

                except Exception as e:
                    logger.error(f"❌ STT Core 루프 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(1)
        except Exception as e:
            logger.error(f"❌ STT Core.run() 최상위 오류: {e}")
            import traceback
            traceback.print_exc()
