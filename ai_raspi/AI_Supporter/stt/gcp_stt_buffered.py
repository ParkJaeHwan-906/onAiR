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


# ========================================
# 디버그 모드 제거됨 - 자동 진행
# ========================================

async def wait_for_next_step_async(step_name: str, step_number: str = ""):
    """디버그 모드 제거됨 - 즉시 진행"""
    pass

class GcpBufferedStt:
    def __init__(self):
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
            print("⚠️ 경고: 오디오 데이터가 모두 0입니다. 정규화 스킵.")
            return audio_data
        
        # 정규화 팩터 계산 (목표 레벨에 맞춤, 클리핑 방지)
        # 16비트 PCM의 최대값은 32767
        max_possible = 32767
        normalize_factor = (target_level * max_possible) / max_abs
        
        # 팩터가 너무 크면 클리핑 방지를 위해 제한
        if normalize_factor > 2.0:
            normalize_factor = 2.0
            print(f"⚠️ 경고: 볼륨이 너무 작아 정규화 팩터를 2.0으로 제한합니다.")
        
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
        
        print(f"🔊 볼륨 정규화:")
        print(f"   정규화 전 평균 절댓값: {avg_before:.2f} (최대: {max_abs})")
        print(f"   정규화 팩터: {normalize_factor:.3f}")
        print(f"   정규화 후 평균 절댓값: {avg_after:.2f}")
        
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
        
        # 3~5초 동안 음성 수집 (타임아웃 처리 포함)
        buffer = []
        start_time = time.time()
        target_duration = self.buffer_duration
        
        # 음성 입력 타임아웃: 3초 동안 실제 음성이 들어오지 않으면 타임아웃
        SPEECH_TIMEOUT_SEC = 3.0
        last_speech_time = start_time  # 마지막으로 실제 음성이 감지된 시간
        MIN_RMS_THRESHOLD = 500.0  # 실제 음성으로 간주하는 최소 RMS 값 (wakeword_detector와 동일)
        
        chunk_count = 0
        while time.time() - start_time < target_duration:
            chunk = mic.read()
            if chunk is None:
                break
            
            # 실제 음성인지 확인 (RMS 값으로)
            has_speech = False
            if isinstance(chunk, np.ndarray):
                # RMS 계산
                audio_array = chunk.astype(np.int16) if chunk.dtype != np.int16 else chunk
                rms = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2))
                if rms >= MIN_RMS_THRESHOLD:
                    has_speech = True
                    last_speech_time = time.time()
                buffer.append(chunk.tobytes())
            else:
                # bytes인 경우 numpy로 변환하여 확인
                try:
                    audio_array = np.frombuffer(chunk, dtype=np.int16)
                    rms = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2))
                    if rms >= MIN_RMS_THRESHOLD:
                        has_speech = True
                        last_speech_time = time.time()
                except:
                    pass
                buffer.append(chunk)
            
            # 타임아웃 확인: 3초 동안 실제 음성이 없으면 타임아웃
            current_time = time.time()
            if current_time - last_speech_time >= SPEECH_TIMEOUT_SEC:
                # 타임아웃 발생
                error_msg = "음성 입력 타임아웃 (3초 동안 음성이 감지되지 않음)"
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

