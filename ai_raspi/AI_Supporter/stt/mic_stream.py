import sounddevice as sd
import numpy as np
import queue
from config import settings


class MicStream:
    def __init__(self):
        self.rate = settings.RATE
        self.chunk = int(settings.RATE * settings.CHUNK_MS / 1000)
        self.channels = settings.CHANNELS
        self.device_index = settings.DEVICE_INDEX
        self.q = queue.Queue()
        self.stream = None
        self.is_paused = False

    def _callback(self, in_data, frames, time_info, status):
        """입력 오디오 데이터를 큐에 저장"""
        if not self.is_paused:
            self.q.put(in_data.copy())

    def start(self):
        """마이크 스트림 시작"""
        self.stream = sd.InputStream(
            samplerate=self.rate,
            channels=self.channels,
            dtype='int16',
            callback=self._callback,
            blocksize=self.chunk,
            device=self.device_index
        )
        self.stream.start()
        print("🔊 마이크 ON (활성 상태)")

    def read(self):
        """큐에서 오디오 버퍼 읽기"""
        data = self.q.get()
        return np.frombuffer(data, dtype=np.int16)

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
