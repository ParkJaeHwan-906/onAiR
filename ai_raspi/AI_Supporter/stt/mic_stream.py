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
    
    def disable_wakeword_callback(self):
        """Wakeword 콜백 비활성화 (STT 세션 중 wakeword 감지 중지)"""
        self.wakeword_callback = None
    
    def enable_wakeword_callback(self, callback):
        """Wakeword 콜백 활성화 (STT 세션 종료 후 wakeword 감지 재개)"""
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
        # 마이크 장치 선택
        device = self.device_index
        if device is None:
            # 기본 입력 장치 자동 선택
            try:
                devices = sd.query_devices()
                # 기본 입력 장치 인덱스 가져오기
                try:
                    default_input_idx = sd.default.device[0]  # (input, output) 튜플
                    if default_input_idx is not None and default_input_idx >= 0:
                        device = default_input_idx
                        default_input = sd.query_devices(device)
                        print(f"🔍 기본 입력 장치 자동 선택: {default_input['name']} (인덱스: {device})")
                    else:
                        raise ValueError("기본 입력 장치가 설정되지 않음")
                except (AttributeError, ValueError, IndexError):
                    # 기본 장치를 찾을 수 없으면 입력 가능한 첫 번째 장치 선택
                    for idx, dev in enumerate(devices):
                        if dev['max_input_channels'] > 0:
                            device = idx
                            print(f"🔍 입력 가능한 장치 선택: {dev['name']} (인덱스: {device})")
                            break
                    else:
                        raise RuntimeError("입력 가능한 마이크 장치를 찾을 수 없습니다.")
            except Exception as e:
                print(f"⚠️ 마이크 장치 자동 선택 실패: {e}")
                print("   사용 가능한 장치 목록:")
                try:
                    devices = sd.query_devices()
                    for idx, dev in enumerate(devices):
                        if dev['max_input_channels'] > 0:
                            print(f"      [{idx}] {dev['name']} (입력 채널: {dev['max_input_channels']})")
                except:
                    pass
                raise RuntimeError(f"마이크 장치를 찾을 수 없습니다. config/settings.py에서 DEVICE_INDEX를 설정하세요.")
        
        try:
            self.stream = sd.InputStream(
                samplerate=self.mic_rate,  # 마이크 실제 샘플레이트 사용
                channels=self.channels,
                dtype='int16',
                callback=self._callback,
                blocksize=self.chunk,
                device=device
            )
            self.stream.start()
            device_info = sd.query_devices(device) if device is not None else None
            device_name = device_info['name'] if device_info else "기본 장치"
            print(f"🔊 마이크 ON (활성 상태) - 샘플레이트: {self.mic_rate}Hz, 장치: {device_name}")
        except Exception as e:
            print(f"❌ 마이크 스트림 시작 실패: {e}")
            print(f"   device_index: {device}")
            print("   사용 가능한 입력 장치 목록:")
            try:
                devices = sd.query_devices()
                for idx, dev in enumerate(devices):
                    if dev['max_input_channels'] > 0:
                        print(f"      [{idx}] {dev['name']} (입력 채널: {dev['max_input_channels']}, 샘플레이트: {dev['default_samplerate']}Hz)")
            except:
                pass
            raise

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

    def is_active(self):
        """마이크 스트림이 활성 상태인지 확인"""
        if self.stream is None:
            return False
        # sounddevice.InputStream은 active 속성을 사용 (is_active() 메서드 없음)
        return self.stream.active and not self.is_paused

    def stop(self):
        """마이크 완전 종료"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
        print("🔇 마이크 종료")
