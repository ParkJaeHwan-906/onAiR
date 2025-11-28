import time
import threading
import logging
import asyncio
import sounddevice as sd
import numpy as np
import wave
import os
from datetime import datetime

logger = logging.getLogger(__name__)

max_retries = 3
retry_delay = 0.5


class AudioStreamer:
    def __init__(self, socketio_client, sample_rate=16000, channels=1,
                 chunk_size=1024, send_chunk=4):

        self.socketio_client = socketio_client
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.send_chunk = send_chunk

        self.buffer = np.zeros((chunk_size * send_chunk,), dtype=np.float32)
        self.buffer_index = 0

        self.stream = None
        self.stream_thread = None

        self.is_streaming = False
        self.lock = threading.Lock()           # 콜백 thread-safe

        # WAV 저장 디렉토리
        self.save_dir = "data/audio"
        os.makedirs(self.save_dir, exist_ok=True)

        self.wav_file = None                   # 현재 파일 객체


    # ---------------------------------------------------
    # WAV 파일 시작
    # ---------------------------------------------------
    def _open_wav_file(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{self.save_dir}/{timestamp}.wav"
        wf = wave.open(path, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(2)            # int16
        wf.setframerate(self.sample_rate)
        self.wav_file = wf
        logger.info(f"🎤 WAV 저장 시작 → {path}")


    # ---------------------------------------------------
    def start(self):
        """기존 스트림이 살아있으면 반드시 정리 후 시작"""

        # -------------------------------
        # 기존 스트림 완전 종료
        # -------------------------------
        self.stop()

        logger.info("🎧 AudioStreamer START 호출")

        self.is_streaming = True
        self.buffer_index = 0

        # WAV 파일 오픈
        # self._open_wav_file()

        # 스트리밍 스레드 시작
        self.stream_thread = threading.Thread(target=self._stream_audio, daemon=True)
        self.stream_thread.start()


    # ---------------------------------------------------
    def stop(self):
        """오디오 스트리밍 완전 종료"""

        if not self.is_streaming and self.stream is None:
            return

        logger.info("🛑 AudioStreamer STOP 호출")

        self.is_streaming = False

        # InputStream 종료
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.warning(f"⚠️ stream close error: {e}")
            finally:
                self.stream = None

        # WAV 파일 닫기
        # if self.wav_file:
        #     try:
        #         self.wav_file.close()
        #     except:
        #         pass
        #     self.wav_file = None

        # 스레드 종료
        if self.stream_thread and self.stream_thread.is_alive():
            if threading.current_thread() != self.stream_thread:
                try:
                    self.stream_thread.join(timeout=1.0)
                except:
                    pass

        self.stream_thread = None


    # ---------------------------------------------------
    def _stream_audio(self):

        def callback(indata, frames, time_info, status):
            if not self.is_streaming:
                return

            # thread-safe
            with self.lock:

                if status:
                    logger.warning(f"⚠️ Audio status: {status}")

                mono = indata[:, 0]
                length = len(mono)

                # WAV 저장 (int16으로)
                # if self.wav_file:
                #     pcm16 = (mono * 32767).astype(np.int16)
                #     self.wav_file.writeframes(pcm16.tobytes())

                # 버퍼 채우기
                if self.buffer_index + length >= len(self.buffer):
                    # 남은 공간 채움
                    self.buffer[self.buffer_index:self.buffer_index + length] = mono[:len(self.buffer) - self.buffer_index]

                    # 전체 버퍼 → bytes 변환
                    timestamp = int(time.time() * 1000)
                    audio_bytes = self.buffer.astype(np.float32).tobytes()

                    # emit
                    self._emit_safe(timestamp, audio_bytes)

                    # 초기화
                    self.buffer_index = 0

                else:
                    self.buffer[self.buffer_index:self.buffer_index + length] = mono
                    self.buffer_index += length

        # -------------------------------
        # 스트림 생성 (재시도 포함)
        # -------------------------------
        for attempt in range(max_retries):

            if not self.is_streaming:
                return

            try:
                self.stream = sd.InputStream(
                    channels=self.channels,
                    samplerate=self.sample_rate,
                    blocksize=self.chunk_size,
                    callback=callback,
                    dtype='float32'
                )
                self.stream.start()
                break

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                else:
                    logger.error("❌ 오디오 스트림 시작 실패")
                    self.stop()
                    return

        # -------------------------------
        # 메인 루프 (stop() 될 때까지)
        # -------------------------------
        while self.is_streaming:
            time.sleep(0.05)


    # ---------------------------------------------------
    def _emit_safe(self, timestamp, frame_bytes):
        """emit_audio_frame을 안전하게 asyncio 루프로 전달"""
        if not self.socketio_client:
            return

        loop = self.socketio_client.loop

        try:
            asyncio.run_coroutine_threadsafe(
                self.socketio_client.emit_audio_frame(timestamp, frame_bytes),
                loop
            )
        except Exception as e:
            logger.error(f"❌ emit audio_frame 실패: {e}")
