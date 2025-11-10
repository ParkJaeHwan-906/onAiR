"""
GCP STT 버퍼링 방식
3~5초 동안 음성을 수집한 후 GCP에 업로드합니다.
"""
import time
import asyncio
import struct
from google.cloud import speech
from config import settings
import numpy as np

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
        
        # 3~5초 동안 음성 수집
        buffer = []
        start_time = time.time()
        target_duration = self.buffer_duration
        
        print(f"🎤 음성 수집 시작 ({target_duration}초)...")
        print(f"   음성 소스: {type(mic).__name__}")
        
        chunk_count = 0
        while time.time() - start_time < target_duration:
            chunk = mic.read()
            if chunk is None:
                print(f"   ⚠️ 음성 데이터 읽기 중단 (chunk={chunk_count})")
                break
            if isinstance(chunk, np.ndarray):
                buffer.append(chunk.tobytes())
            else:
                buffer.append(chunk)

            chunk_count += 1
            # 진행 상황 표시
            elapsed = time.time() - start_time
            if int(elapsed) != int(elapsed - 0.1):  # 1초마다
                print(f"   수집 중... {elapsed:.1f}초 / {target_duration:.1f}초 (청크: {chunk_count})")
        
        if not buffer:
            await broadcaster({
                "type": "error",
                "text": "음성 데이터가 수집되지 않았습니다."
            })
            return
        
        # PCM 데이터 합치기
        audio_data = b''.join(buffer)
        print(f"✅ 음성 수집 완료 ({len(audio_data)} bytes)")
        
        # 디버깅: 오디오 데이터 확인 (첫 100바이트)
        if len(audio_data) > 0:
            print(f"🔍 오디오 데이터 샘플 (처음 100바이트): {audio_data[:100].hex()[:200]}")
            # 오디오 데이터가 모두 0이 아닌지 확인
            if all(b == 0 for b in audio_data[:1000]):
                print("⚠️ 경고: 오디오 데이터의 처음 부분이 모두 0입니다. 파일이 제대로 읽혔는지 확인하세요.")
            else:
                print("✅ 오디오 데이터가 정상적으로 읽혔습니다 (0이 아닌 데이터 포함)")
        
        # 볼륨 정규화 적용
        audio_data = self._normalize_audio_volume(audio_data, target_level=0.8)
        
        # GCP STT 요청
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.rate,
            language_code=self.language,
            enable_automatic_punctuation=True,
        )
        
        audio = speech.RecognitionAudio(content=audio_data)

        print("📤 GCP STT 요청 전송 중...")
        print(f"   오디오 크기: {len(audio_data)} bytes ({len(audio_data) / 2 / self.rate:.2f}초)")
        
        # STT 요청 직후 마이크 종료 (더 이상 음성 수집 불필요)
        mic.pause()
        print("🔇 마이크 OFF (STT 요청 전송 완료, Intent 분류 대기 중)")

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
            if response.results:
                print(f"📋 GCP STT 응답 - 결과 개수: {len(response.results)}")
                for idx, result in enumerate(response.results):
                    transcript = result.alternatives[0].transcript
                    confidence = result.alternatives[0].confidence
                    print(f"📝 STT 결과 [{idx+1}]: {transcript} (신뢰도: {confidence:.2f})")
                    
                    # 대안 결과가 있으면 표시 (디버깅용)
                    if len(result.alternatives) > 1:
                        print(f"   대안 결과:")
                        for alt_idx, alt in enumerate(result.alternatives[1:], 2):
                            print(f"      [{alt_idx}] {alt.transcript} (신뢰도: {alt.confidence:.2f})")
                    
                    # Socket.IO로 결과 전송 (딕셔너리 형태로 전달)
                    stt_data = {
                        "type": "final",
                        "text": transcript,
                        "confidence": confidence
                    }
                    await broadcaster(stt_data)
                    # 텍스트 전송 완료 → 마이크는 이미 OFF 상태 (Intent 분류 중간)
            else:
                print("⚠️ STT 결과가 없습니다.")
                print("   GCP STT API 응답이 비어있습니다. 오디오 데이터를 확인하세요.")
                await broadcaster({
                    "type": "info",
                    "text": "음성이 인식되지 않았습니다."
                })
                # 마이크는 이미 OFF 상태
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ STT 오류: {error_msg}")
            await broadcaster({
                "type": "error",
                "text": error_msg
            })
            # 마이크는 이미 OFF 상태

