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
    
    async def start_main_stt_session(self):
        logger.info("🎤 메인 STT 세션 시작")

        async def broadcaster(msg):
            # STT 결과를 socket_handler로 전달
            if msg["type"] == "final":
                # self.manager.socketio_client.emit_stt_result(msg["text"])
                await self.manager.socketio_client.emit_stt_result(msg)
                logger.info(f"stt result : {msg}")
            elif msg["type"] == "error":
                logger.error(f"STT Error: {msg['text']}")

        try:
            await self.buffered_stt.run(self.mic, broadcaster)
        except Exception as e:
            logger.error(f"❌ STT 세션 오류 또는 타임아웃: {e}")
        
        # STT 종료 → 다시 웨이크워드 모드로 복귀
        logger.info("🔄 STT 종료 → 웨이크워드 모드로 전환")
        self.ignore_wakeword = False
        self.wakeword_detector.resume()
        await self.manager.socketio_client.emit_wakeword_init()



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
                        
                        # if self.wakeword_detector.is_paused:
                        #     self.wakeword_detector.resume()
                        
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
                        # self.manager.wakeword_count += 1
                        
                        # Wakeword 오디오 FastAPI 전송 완료 대기
                        self.wakeword_audio_done.clear()
                        self.wakeword_audio_done.wait()

                        # 현재 단계에서는 wakeword 감지 중지
                        self.ignore_wakeword = True 
                        self.wakeword_detector.pause()
                        self.wakeword_detector.clear_events() 

                        # # STT 감지 시작
                        # self.manager.switch_to_stt()
                        # loop = self.manager.socketio_client.loop
                        # asyncio.run_coroutine_threadsafe(self.start_main_stt_session(), loop)

                        # STT 감지 시작
                        self.manager.switch_to_stt()

                        loop = self.manager.socketio_client.loop
                        logger.info(f"[STT] Loop running: {loop.is_running()}")   # ① loop 상태 확인

                        # ② STT 실제 실행 + future 객체 받기
                        future = asyncio.run_coroutine_threadsafe(
                            self.start_main_stt_session(),
                            loop
                        )

                        # ③ future 예외 또는 완료 로그 찍기
                        def _cb(f):
                            try:
                                result = f.result()  # 내부 예외 있으면 여기서 잡힘
                                logger.info(f"[STT] start_main_stt_session() finished: {result}")
                            except Exception as e:
                                logger.error(f"[STT] start_main_stt_session() ERROR: {e}")

                        future.add_done_callback(_cb)

                    if self.manager.is_rtc_running:
                        self.wakeword_detector.pause()
                        self.wakeword_detector.clear_events()
                        time.sleep(0.1)
                        continue
                    else:
                        # RTC가 종료된 상태인데 아직 ignore_wakeword=True이면 즉시 초기화
                        if self.ignore_wakeword:
                            logger.info("🔄 RTC 종료 감지 → 초기 상태로 복귀")
                            self.reset_to_initial_state()

                    # RTC 모드가 종료되면 초기 상태로 복귀
                    # self.ignore_wakeword = False
                    # self.wakeword_detector.resume()

                except Exception as e:
                    logger.error(f"❌ STT Core 루프 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(1)
        except Exception as e:
            logger.error(f"❌ STT Core.run() 최상위 오류: {e}")
            import traceback
            traceback.print_exc()
