"""
GCP STT 버퍼링 방식
3~5초 동안 음성을 수집한 후 GCP에 업로드합니다.
"""
import time
import asyncio
import struct
import os
from google.cloud import speech
from config import settings
import numpy as np


class GcpBufferedStt:
    def __init__(self):
        # GCP 인증 키 파일 경로 설정
        if hasattr(settings, 'GCP_CREDENTIAL_PATH') and settings.GCP_CREDENTIAL_PATH:
            if os.path.exists(settings.GCP_CREDENTIAL_PATH):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = settings.GCP_CREDENTIAL_PATH
            else:
                raise FileNotFoundError(
                    f"GCP 인증 키 파일을 찾을 수 없습니다: {settings.GCP_CREDENTIAL_PATH}\n"
                    f"파일이 존재하는지 확인하세요."
                )
        
        self.language = settings.LANGUAGE
        self.rate = settings.RATE
        self.client = speech.SpeechClient()
        self.buffer_duration = settings.STT_BUFFER_DURATION_SEC
    
    def _normalize_audio_volume(self, audio_data: bytes, target_level: float = 0.8) -> bytes:
        """
        오디오 데이터의 볼륨을 정규화합니다.
        
        Args:
            audio_data: 16비트 PCM 오디오 데이터 (little-endian)
            target_level: 정규화 목표 레벨 (0.0 ~ 1.0, 기본값: 0.8)
        
        Returns:
            정규화된 오디오 데이터
        """
        if len(audio_data) < 2:
            return audio_data
        
        # 16비트 PCM 샘플로 변환
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = struct.unpack('<h', audio_data[i:i+2])[0]
            samples.append(sample)
        
        if not samples:
            return audio_data
        
        # 최대 절댓값 찾기
        max_abs = max(abs(s) for s in samples)
        
        if max_abs == 0:
            # [25.11.22] 로그 주석 처리 - 재환
            # print("⚠️ 경고: 오디오 데이터가 모두 0입니다. 정규화 스킵.")
            return audio_data
        
        # 정규화 팩터 계산 (목표 레벨에 맞춤, 클리핑 방지)
        # 16비트 PCM의 최대값은 32767
        max_possible = 32767
        normalize_factor = (target_level * max_possible) / max_abs
        
        # 팩터가 너무 크면 클리핑 방지를 위해 제한
        if normalize_factor > 2.0:
            normalize_factor = 2.0
            # [25.11.22] 로그 주석 처리 - 재환
            # print(f"⚠️ 경고: 볼륨이 너무 작아 정규화 팩터를 2.0으로 제한합니다.")
        
        # 정규화 전 볼륨 정보
        avg_before = sum(abs(s) for s in samples) / len(samples)
        
        # 샘플 정규화
        normalized_samples = []
        for sample in samples:
            normalized = int(sample * normalize_factor)
            # 클리핑 방지 (16비트 범위: -32768 ~ 32767)
            normalized = max(-32768, min(32767, normalized))
            normalized_samples.append(normalized)
        
        # 평균 볼륨 확인
        avg_after = sum(abs(s) for s in normalized_samples) / len(normalized_samples)
        
        # [25.11.22] 로그 주석 처리 - 재환
        # print(f"🔊 볼륨 정규화:")
        # print(f"   정규화 전 평균 절댓값: {avg_before:.2f} (최대: {max_abs})")
        # print(f"   정규화 팩터: {normalize_factor:.3f}")
        # print(f"   정규화 후 평균 절댓값: {avg_after:.2f}")
        
        # 바이트로 변환
        normalized_audio = b''.join(struct.pack('<h', s) for s in normalized_samples)
        
        return normalized_audio

    async def run(self, mic, broadcaster):
        """
        마이크에서 음성을 수집하여 GCP STT에 업로드합니다.
        
        Args:
            mic: MicStream 인스턴스
            broadcaster: 결과를 전송할 함수
        """
        # 마이크 안정화 대기 (0.1초)
        await asyncio.sleep(0.1)
        
        # 큐에 쌓인 오래된 데이터 제거 (이전 세션의 잔여 데이터 방지)
        if hasattr(mic, 'q'):
            while not mic.q.empty():
                try:
                    mic.q.get_nowait()
                except:
                    break
        
        # 모바일 오디오 재생 시간(3-5초) + 사용자 말 시작 시간(1-2초)을 고려하여 음성 수집
        buffer = []
        start_time = time.time()
        target_duration = self.buffer_duration
        
        # 음성 입력 타임아웃: 12초 동안 실제 음성이 들어오지 않으면 타임아웃
        # (모바일 오디오 재생 시간 + 사용자 말 시작 시간을 고려하여 충분한 시간 제공)
        SPEECH_TIMEOUT_SEC = 12.0
        # 초기 대기 시간: 모바일 오디오 재생 시간(3-5초) + 사용자 말 시작 시간(1-2초) = 6초
        # (모바일 오디오 재생 완료를 기다리지 않고 버퍼링 STT가 시작되므로 충분한 시간 제공)
        INITIAL_GRACE_PERIOD = 6.0
        last_speech_time = start_time  # 마지막으로 실제 음성이 감지된 시간
        MIN_RMS_THRESHOLD = 500.0  # 실제 음성으로 간주하는 최소 RMS 값 (wakeword_detector와 동일)
        
        chunk_count = 0
        # 청크 읽기 타임아웃: 0.1초 (큐가 비어있을 때 무한 대기 방지)
        CHUNK_READ_TIMEOUT = 0.1
        
        while time.time() - start_time < target_duration:
            # 타임아웃을 사용하여 큐가 비어있을 때 무한 대기 방지
            chunk = mic.read(timeout=CHUNK_READ_TIMEOUT)
            if chunk is None:
                # 타임아웃 발생 (큐가 비어있음) - 계속 루프 진행하여 전체 타임아웃 체크
                current_time = time.time()
                elapsed_time = current_time - start_time
                
                # 전체 타임아웃 체크 (초기 대기 시간 이후)
                if elapsed_time > INITIAL_GRACE_PERIOD:
                    if current_time - last_speech_time >= SPEECH_TIMEOUT_SEC:
                        # 타임아웃 발생
                        error_msg = f"음성 입력 타임아웃 ({int(SPEECH_TIMEOUT_SEC)}초 동안 음성이 감지되지 않음)"
                        await broadcaster({
                            "type": "error",
                            "text": error_msg
                        })
                        raise ValueError(error_msg)
                
                # 타임아웃이 아니면 계속 루프 진행
                continue
            
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # 실제 음성인지 확인 (RMS 값으로)
            has_speech = False
            if isinstance(chunk, np.ndarray):
                # RMS 계산
                audio_array = chunk.astype(np.int16) if chunk.dtype != np.int16 else chunk
                rms = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2))
                if rms >= MIN_RMS_THRESHOLD:
                    has_speech = True
                    last_speech_time = current_time
                buffer.append(chunk.tobytes())
            else:
                # bytes인 경우 numpy로 변환하여 확인
                try:
                    audio_array = np.frombuffer(chunk, dtype=np.int16)
                    rms = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2))
                    if rms >= MIN_RMS_THRESHOLD:
                        has_speech = True
                        last_speech_time = current_time
                except:
                    pass
                buffer.append(chunk)
            
            # 타임아웃 확인: 초기 대기 시간 이후에만 타임아웃 체크
            # (초기 대기 시간 동안은 사용자가 말을 시작할 시간을 제공)
            # 주의: chunk가 None일 때는 이미 위에서 타임아웃 체크를 했으므로 여기서는 음성이 있을 때만 체크
            if elapsed_time > INITIAL_GRACE_PERIOD:
                if current_time - last_speech_time >= SPEECH_TIMEOUT_SEC:
                    # 타임아웃 발생
                    error_msg = f"음성 입력 타임아웃 ({int(SPEECH_TIMEOUT_SEC)}초 동안 음성이 감지되지 않음)"
                    await broadcaster({
                        "type": "error",
                        "text": error_msg
                    })
                    raise ValueError(error_msg)
        
        if not buffer:
            await broadcaster({
                "type": "error",
                "text": "음성 데이터가 수집되지 않았습니다."
            })
            return
        
        # PCM 데이터 합치기
        audio_data = b''.join(buffer)
        
        # 볼륨 정규화 적용
        try:
            audio_data = self._normalize_audio_volume(audio_data, target_level=0.8)
        except Exception as e:
            pass  # 볼륨 정규화 실패해도 계속 진행
        
        # GCP STT 요청
        try:
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.rate,
                language_code=self.language,
                enable_automatic_punctuation=True,
            )
            audio = speech.RecognitionAudio(content=audio_data)
        except Exception as e:
            raise

        # 오디오 길이 계산 및 검증
        audio_samples = len(audio_data) // 2
        audio_duration_sec = audio_samples / self.rate
        
        # GCP STT 동기 API 제한: 1분(60초) 초과 시 오디오 자르기
        MAX_DURATION_SEC = 60.0
        if audio_duration_sec > MAX_DURATION_SEC:
            max_samples = int(MAX_DURATION_SEC * self.rate * 2)
            audio_data = audio_data[:max_samples]
        
        # 주의: 마이크는 계속 ON 상태로 유지됨
        # 버퍼링 STT 세션 종료는 FastAPI에서 stop_buffered_stt 이벤트로 처리됨

        def blocking_recognize():
            try:
                response = self.client.recognize(config=config, audio=audio)
                return response
            except Exception as e:
                raise e

        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(None, blocking_recognize)
            
            # 결과 처리
            if response.results and len(response.results) > 0:
                has_valid_result = False
                for result in response.results:
                    if result.alternatives and len(result.alternatives) > 0:
                        transcript = result.alternatives[0].transcript
                        confidence = result.alternatives[0].confidence
                        
                        # 빈 텍스트 체크
                        if transcript and transcript.strip():
                            has_valid_result = True
                            # Socket.IO로 결과 전송
                            stt_data = {
                                "type": "final",
                                "text": transcript,
                                "confidence": confidence
                            }
                            await broadcaster(stt_data)
                            # 로그 최소화: 정상 전송 시 로그 제거
                
                # 유효한 결과가 없으면 예외 발생 (wakeword 대기 상태로 복귀)
                if not has_valid_result:
                    error_msg = "STT 결과가 None이거나 빈 텍스트입니다"
                    # 로그 최소화: 경고 로그 제거
                    await broadcaster({
                        "type": "error",
                        "text": error_msg
                    })
                    raise ValueError(error_msg)
            else:
                # 결과가 없으면 예외 발생 (wakeword 대기 상태로 복귀)
                error_msg = "음성이 인식되지 않았습니다 (STT 결과 없음)"
                # 로그 최소화: 경고 로그 제거
                await broadcaster({
                    "type": "info",
                    "text": error_msg
                })
                raise ValueError(error_msg)
                
        except ValueError as e:
            # STT 결과가 None이거나 빈 텍스트인 경우
            raise  # 상위로 전파하여 wakeword 대기 상태로 복귀
        except Exception as e:
            error_msg = str(e)
            # 로그 최소화: 오류 로그는 메인 루프에서 처리
            await broadcaster({
                "type": "error",
                "text": error_msg
            })
            # 마이크는 계속 ON 상태로 유지됨
            raise  # 상위로 예외 전파하여 wakeword 대기 상태로 복귀

    # wakeword 교차검증용, 이전의 음성 데이터로 STT 
    # async def transcribe_bytes(self, audio_data: bytes, broadcaster):
    #     """
    #     MicStream 없이 raw PCM (bytes) 데이터를 바로 STT 요청.
    #     wakeword 교차 검증 용도.

    #     Args:
    #         audio_data: 16bit PCM little-endian bytes
    #         broadcaster: STT 결과 처리 콜백 함수
    #     """
    #     if not audio_data or len(audio_data) < 1000:
    #         await broadcaster({
    #             "type": "error",
    #             "text": "오디오 데이터가 너무 짧습니다."
    #         })
    #         return

    #     # 최소 길이 보정: 1.5초 미만이면 무음으로 패딩
    #     min_sec = 1.5
    #     min_bytes = int(self.rate * min_sec * 2)  # 16bit = 2 bytes
    #     if len(audio_data) < min_bytes:
    #         pad_len = min_bytes - len(audio_data)
    #         audio_data = audio_data + (b"\x00" * pad_len)

    #     try:
    #         audio_data = self._normalize_audio_volume(audio_data, target_level=0.8)
    #     except Exception:
    #         pass

    #     config = speech.RecognitionConfig(
    #         encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    #         sample_rate_hertz=self.rate,
    #         language_code=self.language,
    #         enable_automatic_punctuation=False,
    #         alternative_language_codes=["en-US"],
    #         model="latest_short",  # 짧은 오디오에 적합한 모델
    #     )
    #     audio = speech.RecognitionAudio(content=audio_data)

    #     def blocking_call():
    #         try:
    #             return self.client.recognize(config=config, audio=audio)
    #         except Exception as e:
    #             raise e

    #     loop = asyncio.get_running_loop()

    #     try:
    #         audio_samples = len(audio_data) // 2
    #         audio_duration_sec = audio_samples / self.rate
    #         import logging
    #         logger = logging.getLogger(__name__)
    #         logger.info(f"🎵 STT 요청: 오디오 길이={len(audio_data)} bytes, 샘플={audio_samples}, 지속시간={audio_duration_sec:.2f}초")

    #         response = await loop.run_in_executor(None, blocking_call)

    #         logger.info(f"📥 GCP STT 응답 수신: results 개수={len(response.results) if response.results else 0}")

    #         if not response.results:
    #             logger.warning("⚠️ GCP STT 응답에 results가 없음")
    #             await broadcaster({"type": "error", "text": "STT 결과 없음"})
    #             return

    #         result = response.results[0]
    #         logger.info(f"📋 첫 번째 result: alternatives 개수={len(result.alternatives) if result.alternatives else 0}")

    #         if not result.alternatives:
    #             logger.warning("⚠️ GCP STT 응답에 alternatives가 없음")
    #             await broadcaster({"type": "error", "text": "STT 결과 없음"})
    #             return

    #         transcript = result.alternatives[0].transcript
    #         confidence = result.alternatives[0].confidence
    #         logger.info(f"📝 GCP STT 전사 결과: '{transcript}' (신뢰도: {confidence})")

    #         if not transcript.strip():
    #             logger.warning("⚠️ GCP STT 전사 결과가 빈 문자열")
    #             await broadcaster({"type": "error", "text": "빈 텍스트"})
    #             return

    #         await broadcaster({
    #             "type": "final",
    #             "text": transcript,
    #             "confidence": confidence
    #         })

    #     except Exception as e:
    #         import logging
    #         logger = logging.getLogger(__name__)
    #         logger.error(f"❌ GCP STT 호출 중 예외: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         await broadcaster({
    #             "type": "error",
    #             "text": str(e)
    #         })
    #         raise

    async def transcribe_bytes(self, audio_data: bytes, broadcaster):
        """
        MicStream 없이 raw PCM (bytes) 데이터를 바로 STT 요청.
        - MicStream 구조에 맞춰 16kHz, int16 mono 전제
        - 패딩은 앞/뒤 균등 분배
        - numpy 기반 안전 정규화
        - PCM format 검사 포함
        """

        import logging
        logger = logging.getLogger(__name__)

        # =============================
        # 1) 데이터 길이 기본 검증
        # =============================
        if not audio_data or len(audio_data) < 1000:
            await broadcaster({"type": "error", "text": "오디오 데이터가 너무 짧습니다"})
            return

        # =============================
        # 2) PCM 변환 및 유효성 체크
        # =============================
        try:
            pcm = np.frombuffer(audio_data, dtype=np.int16)
        except Exception:
            await broadcaster({"type": "error", "text": "PCM 변환 실패 (int16 아님)"})
            return

        if pcm.size == 0:
            await broadcaster({"type": "error", "text": "PCM 샘플 없음"})
            return

        # mono 체크 (MicStream은 항상 mono이므로 경고만)
        if pcm.ndim != 1:
            logger.warning("⚠ PCM이 1차원이 아님 (mono 아님 가능성 있음)")

        # =============================
        # 3) 최소 길이 1.5초 미만이면 중앙 패딩
        # =============================
        min_sec = 1.5
        min_bytes = int(self.rate * min_sec * 2)

        if len(audio_data) < min_bytes:
            diff = min_bytes - len(audio_data)
            left = diff // 2
            right = diff - left
            audio_data = (b"\x00" * left) + audio_data + (b"\x00" * right)
            pcm = np.frombuffer(audio_data, dtype=np.int16)

        # =============================
        # 4) numpy 기반 볼륨 정규화
        # =============================
        try:
            float_pcm = pcm.astype(np.float32)
            peak = np.max(np.abs(float_pcm))

            if peak > 0:
                factor = (0.8 * 32767) / peak
                factor = min(factor, 2.0)  # clipping 제한
                float_pcm *= factor
                float_pcm = np.clip(float_pcm, -32768, 32767)
                pcm = float_pcm.astype(np.int16)

            audio_data = pcm.tobytes()

        except Exception as e:
            logger.warning(f"⚠ 정규화 실패: {e}")

        # =============================
        # 5) PCM duration 계산
        # =============================
        samples = len(audio_data) // 2
        duration = samples / self.rate
        logger.info(f"🎵 STT 요청: bytes={len(audio_data)}, 샘플={samples}, 길이={duration:.2f}s")

        # =============================
        # 6) GCP STT 호출 구성
        # =============================
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.rate,   # MicStream과 동일: 16000
            language_code=self.language,
            enable_automatic_punctuation=False,
            alternative_language_codes=["en-US"],
            model="latest_short",
        )
        audio = speech.RecognitionAudio(content=audio_data)

        def blocking():
            return self.client.recognize(config=config, audio=audio)

        loop = asyncio.get_running_loop()

        # =============================
        # 7) 실제 GCP 요청
        # =============================
        try:
            response = await loop.run_in_executor(None, blocking)

            result_count = len(response.results)
            logger.info(f"📥 GCP STT results={result_count}")

            if result_count == 0:
                await broadcaster({"type": "error", "text": "STT 결과 없음"})
                return

            result = response.results[0]

            if not result.alternatives:
                await broadcaster({"type": "error", "text": "STT 결과 없음"})
                return

            transcript = result.alternatives[0].transcript
            confidence = result.alternatives[0].confidence

            if not transcript.strip():
                await broadcaster({"type": "error", "text": "빈 텍스트"})
                return

            logger.info(f"📝 결과: '{transcript}' (신뢰도={confidence})")

            await broadcaster({
                "type": "final",
                "text": transcript,
                "confidence": confidence,
            })

        except Exception as e:
            logger.error(f"❌ GCP STT 예외: {e}")
            await broadcaster({"type": "error", "text": str(e)})
            raise

