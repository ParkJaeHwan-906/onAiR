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
        - 초기 무음 허용: 1초
        - 무음 타임아웃: 2초
        - 전체 버퍼링 시간: settings.STT_BUFFER_DURATION_SEC (권장: 4초)
        """

        # 안정화 대기
        await asyncio.sleep(0.1)

        # 이전 잔여 데이터 제거
        if hasattr(mic, 'q'):
            while not mic.q.empty():
                try:
                    mic.q.get_nowait()
                except:
                    break

        # 파라미터 설정
        INITIAL_GRACE_PERIOD = 1.0
        SPEECH_TIMEOUT_SEC = 3.0
        MIN_RMS_THRESHOLD = 500.0
        CHUNK_READ_TIMEOUT = 0.1

        buffer = []
        start_time = time.time()
        last_speech_time = start_time
        target_duration = self.buffer_duration

        # --------------------------------------------------
        # 1) 입력 버퍼링
        # --------------------------------------------------
        while time.time() - start_time < target_duration:

            current_time = time.time()
            elapsed_time = current_time - start_time
            remaining = round(target_duration - elapsed_time, 2)

            # 🔵 카운트다운 출력
            print(f"[STT 버퍼링] 종료까지 남은 시간: {remaining}s", flush=True)

            # non-blocking read
            chunk = mic.read(timeout=CHUNK_READ_TIMEOUT)

            # ----------- chunk 없음 (큐 비었음) -----------
            if chunk is None:
                if elapsed_time > INITIAL_GRACE_PERIOD:
                    if current_time - last_speech_time >= SPEECH_TIMEOUT_SEC:
                        error_msg = "음성 입력 타임아웃 (2초 동안 음성이 감지되지 않음)"
                        await broadcaster({"type": "error", "text": error_msg})
                        raise ValueError(error_msg)
                continue

            # ----------- chunk 있음 (오디오 들어옴) -----------
            try:
                audio_array = chunk.astype(np.int16) if isinstance(chunk, np.ndarray) \
                    else np.frombuffer(chunk, dtype=np.int16)
            except:
                continue

            rms = float(np.sqrt(np.mean(audio_array.astype(np.float64) ** 2)))

            if rms >= MIN_RMS_THRESHOLD:
                last_speech_time = current_time
            else:
                continue

            buffer.append(audio_array.tobytes())

            if elapsed_time > INITIAL_GRACE_PERIOD:
                if current_time - last_speech_time >= SPEECH_TIMEOUT_SEC:
                    error_msg = "음성 입력 타임아웃 (2초 동안 음성이 감지되지 않음)"
                    await broadcaster({"type": "error", "text": error_msg})
                    raise ValueError(error_msg)

        # --------------------------------------------------
        # 2) 버퍼 없음 → 에러 종료
        # --------------------------------------------------
        if not buffer:
            await broadcaster({"type": "error", "text": "음성 데이터가 수집되지 않았습니다."})
            return

        # --------------------------------------------------
        # 3) PCM 결합 및 정규화
        # --------------------------------------------------
        audio_data = b"".join(buffer)

        try:
            audio_data = self._normalize_audio_volume(audio_data, target_level=0.8)
        except:
            pass

        # --------------------------------------------------
        # 4) GCP STT 호출
        # --------------------------------------------------
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.rate,
            language_code=self.language,
            enable_automatic_punctuation=True,
        )
        audio = speech.RecognitionAudio(content=audio_data)

        def blocking_recognize():
            return self.client.recognize(config=config, audio=audio)

        loop = asyncio.get_running_loop()

        try:
            response = await loop.run_in_executor(None, blocking_recognize)

            if not response.results:
                await broadcaster({"type": "error", "text": "STT 결과 없음"})
                raise ValueError("STT 결과 없음")

            result = response.results[0]

            if not result.alternatives:
                await broadcaster({"type": "error", "text": "STT 결과 없음"})
                raise ValueError("STT 결과 없음")

            transcript = result.alternatives[0].transcript
            confidence = result.alternatives[0].confidence

            if not transcript.strip():
                await broadcaster({"type": "error", "text": "빈 텍스트"})
                raise ValueError("빈 텍스트")

            await broadcaster({
                "type": "final",
                "text": transcript,
                "confidence": confidence
            })

        except Exception as e:
            await broadcaster({"type": "error", "text": str(e)})
            raise



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
            sample_rate_hertz=self.rate,
            language_code=self.language,
            enable_automatic_punctuation=True,
            use_enhanced=True,
            model="command_and_search",
            speech_contexts=[
                speech.SpeechContext(phrases=["온에어", "OnAir", "오네요", "보네요", "에어", "오내요", "보내요"], boost=23.0)
            ],
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

