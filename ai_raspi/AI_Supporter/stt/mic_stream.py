import sounddevice as sd
import numpy as np
import queue
from scipy import signal
from config import settings


class MicStream:
    def __init__(self):
        self.mic_rate = settings.MIC_RATE  # 마이크 실제 샘플레이트 (48000Hz)
        self.stt_rate = settings.RATE       # STT용 샘플레이트 (16000Hz)
        self.rate = self.stt_rate           # 호환성을 위한 속성 (GCP STT는 16000Hz 기대)
        self.chunk = int(self.mic_rate * settings.CHUNK_MS / 1000)
        self.channels = settings.CHANNELS
        self.device_index = settings.DEVICE_INDEX
        self.q = queue.Queue()
        self.stream = None
        self.is_paused = False
        self.wakeword_callback = None  # Wakeword 감지기 콜백

    def set_wakeword_callback(self, callback):
        """Wakeword 감지기 콜백 설정 (16000Hz 오디오 데이터를 받음)"""
        self.wakeword_callback = callback

    def _callback(self, in_data, frames, time_info, status):
        """입력 오디오 데이터를 큐에 저장 및 Wakeword 감지기에 전달"""
        if not self.is_paused:
            self.q.put(in_data.copy())
            
            # Wakeword 감지기에 오디오 데이터 전달 (16000Hz로 리샘플링)
            if self.wakeword_callback is not None:
                audio_48k = np.frombuffer(in_data, dtype=np.int16)
                # 48000Hz → 16000Hz 리샘플링
                if self.mic_rate != self.stt_rate:
                    num_samples_16k = int(len(audio_48k) * self.stt_rate / self.mic_rate)
                    audio_16k = signal.resample(audio_48k.astype(np.float32), num_samples_16k)
                    audio_16k_int = audio_16k.astype(np.int16)
                else:
                    audio_16k_int = audio_48k
                
                # Wakeword 감지기 콜백 호출
                try:
                    self.wakeword_callback(audio_16k_int)
                except Exception as e:
                    # Wakeword 감지기 오류는 무시 (메인 스트림에 영향 없음)
                    pass

    def start(self):
        """마이크 스트림 시작 (마이크는 실제 샘플레이트로 열기)"""
        self.stream = sd.InputStream(
            samplerate=self.mic_rate,  # 마이크 실제 샘플레이트 사용
            channels=self.channels,
            dtype='int16',
            callback=self._callback,
            blocksize=self.chunk,
            device=self.device_index
        )
        self.stream.start()
        print(f"🔊 마이크 ON (활성 상태) - 샘플레이트: {self.mic_rate}Hz")

    def read(self):
        """큐에서 오디오 버퍼 읽기 (16000Hz로 리샘플링)"""
        data = self.q.get()
        audio_48k = np.frombuffer(data, dtype=np.int16)
        
        # 48000Hz → 16000Hz 리샘플링 (3:1 비율)
        if self.mic_rate != self.stt_rate:
            num_samples_16k = int(len(audio_48k) * self.stt_rate / self.mic_rate)
            audio_16k = signal.resample(audio_48k.astype(np.float32), num_samples_16k)
            return audio_16k.astype(np.int16)
        else:
            return audio_48k

    def pause(self):
        """마이크 입력 일시 정지"""
        if self.stream and not self.is_paused:
            self.is_paused = True
            print("🔇 마이크 OFF (대기 상태)")

    def resume(self):
        """마이크 입력 재개"""
        if self.stream and self.is_paused:
            # 이전 데이터 제거
            while not self.q.empty():
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    break
            self.is_paused = False
            print("🔊 마이크 ON (활성 상태)")

    def stop(self):
        """마이크 완전 종료"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
        print("🔇 마이크 종료")
