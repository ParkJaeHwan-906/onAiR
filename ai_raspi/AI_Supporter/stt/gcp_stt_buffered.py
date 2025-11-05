"""
GCP STT 버퍼링 방식
3~5초 동안 음성을 수집한 후 GCP에 업로드합니다.
"""
import time
import asyncio
from google.cloud import speech
from config import settings

class GcpBufferedStt:
    def __init__(self):
        self.language = settings.LANGUAGE
        self.rate = settings.RATE
        self.client = speech.SpeechClient()
        self.buffer_duration = settings.STT_BUFFER_DURATION_SEC

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
        
        while time.time() - start_time < target_duration:
            chunk = mic.read()
            if chunk is None:
                break
            buffer.append(chunk)
            # 진행 상황 표시
            elapsed = time.time() - start_time
            if int(elapsed) != int(elapsed - 0.1):  # 1초마다
                print(f"   수집 중... {elapsed:.1f}초 / {target_duration:.1f}초")
        
        if not buffer:
            await broadcaster('{"type":"error","text":"음성 데이터가 수집되지 않았습니다."}')
            return
        
        # PCM 데이터 합치기
        audio_data = b''.join(buffer)
        print(f"✅ 음성 수집 완료 ({len(audio_data)} bytes)")
        
        # GCP STT 요청
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.rate,
            language_code=self.language,
            enable_automatic_punctuation=True,
        )
        
        audio = speech.RecognitionAudio(content=audio_data)

        print("📤 GCP STT 요청 전송 중...")
        
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
                for result in response.results:
                    transcript = result.alternatives[0].transcript
                    confidence = result.alternatives[0].confidence
                    print(f"📝 STT 결과: {transcript} (신뢰도: {confidence:.2f})")
                    
                    # WebSocket으로 결과 전송
                    await broadcaster(f'{{"type":"final","text":"{transcript}","confidence":{confidence}}}')
                    # 텍스트 전송 완료 → 마이크는 이미 OFF 상태 (Intent 분류 중간)
            else:
                print("⚠️ STT 결과가 없습니다.")
                await broadcaster('{"type":"info","text":"음성이 인식되지 않았습니다."}')
                # 마이크는 이미 OFF 상태
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ STT 오류: {error_msg}")
            await broadcaster(f'{{"type":"error","text":"{error_msg}"}}')
            # 마이크는 이미 OFF 상태

