import pyaudio
import queue
import time
from config import settings

class MicStream:
    def __init__(self):
        self.rate = settings.RATE
        self.chunk = int(settings.RATE * settings.CHUNK_MS / 1000)
        self.channels = settings.CHANNELS
        self.device_index = settings.DEVICE_INDEX
        self.pa = pyaudio.PyAudio()
        self.q = queue.Queue()
        self.stream = None

    def start(self):
        def callback(in_data, frame_count, time_info, status):
            self.q.put(in_data)
            return (None, pyaudio.paContinue)

        self.stream = self.pa.open(format=pyaudio.paInt16,
                                   channels=self.channels,
                                   rate=self.rate,
                                   input=True,
                                   frames_per_buffer=self.chunk,
                                   input_device_index=self.device_index,
                                   stream_callback=callback)
        self.stream.start_stream()

    def read(self):
        return self.q.get()

    def pause(self):
        """마이크 스트림 일시 정지 (대기 상태)"""
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            print("🔇 마이크 OFF (대기 상태)")
    
    def resume(self):
        """마이크 스트림 재개 (활성 상태)"""
        if self.stream and not self.stream.is_active():
            # 큐 초기화 (이전 데이터 제거)
            while not self.q.empty():
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    break
            self.stream.start_stream()
            print("🔊 마이크 ON (활성 상태)")
    
    def stop(self):
        """마이크 스트림 완전 종료"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.pa.terminate()
        print("🔇 마이크 종료")
