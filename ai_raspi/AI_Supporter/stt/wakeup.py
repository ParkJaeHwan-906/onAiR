import threading
import queue
import numpy as np
import scipy.signal
from scipy.fftpack import dct
import tflite_runtime.interpreter as tflite
import time

# -----------------------------
# 설정
# -----------------------------
SAMPLE_RATE = 16000
N_FFT = 400
HOP = 160
N_MFCC = 40
TARGET_FRAMES = 98
WAKEWORD_THRESHOLD = 0.5   # 모델 신뢰도 임계값
LABELS = ["onair", "negative"]

# VAD 임계값 (int16 -> float 변환 후 기준)
# 0.01은 int16 기준 약 327 정도의 크기입니다.
SPEECH_THRESHOLD = 0.01 

# -----------------------------
# 전처리 유틸리티 (Mel Filterbank & MFCC)
# -----------------------------
def hz_to_mel(hz):
    return 2595 * np.log10(1 + hz / 700.0)

def mel_to_hz(mel):
    return 700 * (10**(mel / 2595.0) - 1)

def build_mel_filterbank():
    n_mels = N_MFCC
    fmin = 0
    fmax = SAMPLE_RATE / 2

    mel_pts = np.linspace(hz_to_mel(fmin), hz_to_mel(fmax), n_mels + 2)
    hz_pts = mel_to_hz(mel_pts)
    bin_pts = np.floor((N_FFT + 1) * hz_pts / SAMPLE_RATE).astype(int)

    fb = np.zeros((n_mels, N_FFT//2 + 1))
    for i in range(1, n_mels + 1):
        left, center, right = bin_pts[i-1], bin_pts[i], bin_pts[i+1]
        for j in range(left, center):
            fb[i-1, j] = (j - left) / (center - left)
        for j in range(center, right):
            fb[i-1, j] = (right - j) / (right - center)
    return fb

MEL_FBANK = build_mel_filterbank()

def mfcc_exact(audio):
    """
    scipy 기반 MFCC 추출 (학습 코드와 동일 로직)
    Input: audio (float32 numpy array)
    """
    audio = audio.astype(np.float32)
    
    # 1. Pre-emphasis
    pre = 0.97
    audio = np.append(audio[0], audio[1:] - pre * audio[:-1])

    # 2. STFT
    _, _, Zxx = scipy.signal.stft(
        audio, fs=SAMPLE_RATE, window='hann',
        nperseg=N_FFT, noverlap=N_FFT - HOP,
        padded=False, boundary=None
    )

    # 3. Mel Spectrogram
    S = np.abs(Zxx) ** 2
    mel = np.dot(MEL_FBANK, S)
    mel = np.maximum(mel, 1e-10)
    mel_db = 10.0 * np.log10(mel).T

    # 4. DCT
    mfcc = dct(mel_db, type=2, axis=1, norm='ortho')[:, :N_MFCC]
    
    # 5. Normalization
    mfcc = (mfcc - mfcc.mean()) / (mfcc.std() + 1e-6)

    # 6. Padding/Truncating
    if mfcc.shape[0] < TARGET_FRAMES:
        mfcc = np.pad(mfcc, ((0, TARGET_FRAMES - mfcc.shape[0]), (0, 0)))
    else:
        mfcc = mfcc[:TARGET_FRAMES]

    return np.expand_dims(mfcc.astype(np.float32), (0, -1))

def is_speech(chunk):
    """RMS 기반 VAD"""
    rms = np.sqrt(np.mean(chunk ** 2))
    # print(f"RMS={rms:.4f}") # 디버깅 필요시 주석 해제
    return rms > SPEECH_THRESHOLD

# -----------------------------
# Wakeword Detector 클래스
# -----------------------------
class WakewordDetector:
    def __init__(self, model_path=None):
        if model_path is None:
            # 기본 경로 설정
            model_path = "/home/pi/wakeword_onair_mfcc_fp16.tflite"
            
        self.model_path = model_path
        
        # TFLite 모델 로드
        try:
            self.interpreter = tflite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()[0]
            self.output_details = self.interpreter.get_output_details()[0]
            print(f"✅ Wakeword 모델 로드 성공: {self.model_path}")
        except Exception as e:
            print(f"❌ Wakeword 모델 로드 실패: {e}")
            self.interpreter = None

        # 상태 변수들
        self.recording = False
        self.speech_buffer = []            # 전체 음성 버퍼 (Float32)
        self.recent_detected_audio = None  # 감지된 오디오 저장용 (Float32)
        self.wakeword_detected_inside = False
        
        # 최적화용 변수 (Sliding Window)
        self.samples_since_last_check = 0 
        self.CHECK_INTERVAL = 8000         # 0.5초마다 검사

        # 스레드 제어
        self.detect_queue = queue.Queue(maxsize=1)
        self.is_running = False
        self.is_paused = False  # stt_core에서 확인하는 속성
        self.thread = threading.Thread(target=self._detect_loop, daemon=True)

    def _predict(self, audio):
        if self.interpreter is None:
            return np.array([0.0, 1.0]) # 모델 없으면 negative

        x = mfcc_exact(audio) 
        self.interpreter.set_tensor(self.input_details["index"], x)
        self.interpreter.invoke()
        return self.interpreter.get_tensor(self.output_details["index"])[0]

    def _run_inference(self):
        """실제 추론 수행 (버퍼 데이터 사용)"""
        # 버퍼가 너무 짧으면 패스 (최소 0.25초)
        if len(self.speech_buffer) < 4000:
            return

        # 가장 최근 1초(16000개) 데이터만 가져오기
        audio_now = np.array(self.speech_buffer[-16000:], dtype=np.float32)
        
        # 1초보다 짧으면 앞에 0으로 패딩
        if len(audio_now) < 16000:
            audio_now = np.pad(audio_now, (16000 - len(audio_now), 0))

        pred = self._predict(audio_now)
        
        # 임계값 확인
        if LABELS[np.argmax(pred)] == "onair" and np.max(pred) > WAKEWORD_THRESHOLD:
            self.wakeword_detected_inside = True
            print(f"⚡ Wakeword 내부 감지됨! (확률: {np.max(pred):.2f})")

    def process_audio_chunk(self, chunk):
        """MicStream에서 호출되는 콜백 함수"""
        if self.is_paused or not self.is_running:
            return

        # 1. 데이터 정규화 (int16 -> float32)
        # MicStream은 int16 데이터를 보내줍니다.
        if chunk.dtype == np.int16:
            chunk = chunk.astype(np.float32) / 32768.0
        else:
            chunk = chunk.astype(np.float32)

        # 2. VAD 판별
        speech = is_speech(chunk)

        # --- 말하기 시작 ---
        if speech and not self.recording:
            self.recording = True
            self.speech_buffer = []
            self.samples_since_last_check = 0
            # print("🗣️ Speech Start")

        # --- 말하는 중 ---
        if self.recording:
            self.speech_buffer.extend(chunk)
            self.samples_since_last_check += len(chunk)

            # ★ 최적화: 0.5초마다 추론 (CPU 부하 감소)
            if self.samples_since_last_check >= self.CHECK_INTERVAL:
                self._run_inference()
                self.samples_since_last_check = 0

        # --- 말하기 끝 ---
        if not speech and self.recording:
            self.recording = False
            # print("🤐 Speech End")

            # 말이 끝나는 순간 마지막 구간 한 번 더 확인
            self._run_inference()

            if self.wakeword_detected_inside:
                # 결과 저장 (Float32 상태로 저장)
                self.recent_detected_audio = np.array(self.speech_buffer, dtype=np.float32)
                self.detect_queue.put(True)
            
            # 초기화
            self.wakeword_detected_inside = False
            self.speech_buffer = []
            self.samples_since_last_check = 0

    def _detect_loop(self):
        """메인 스레드 유지용 (실제 감지는 callback에서 수행됨)"""
        while self.is_running:
            time.sleep(0.1)

    def start(self):
        if not self.is_running:
            self.is_running = True
            if not self.thread.is_alive():
                self.thread.start()
            print("🎤 Wakeword 감지기 시작")

    def stop(self):
        self.is_running = False
        self.is_paused = False
        print("🛑 Wakeword 감지기 종료")

    def pause(self):
        """감지 일시 중지 (stt_core에서 호출)"""
        self.is_paused = True
        # print("⏸️ Wakeword 감지 일시 중지")

    def resume(self):
        """감지 재개 (stt_core에서 호출)"""
        self.is_paused = False
        self.recording = False     # 상태 리셋
        self.speech_buffer = []    # 버퍼 리셋
        # print("▶️ Wakeword 감지 재개")

    def wait_for_wakeword(self, timeout=None):
        try:
            return self.detect_queue.get(timeout=timeout)
        except queue.Empty:
            return False

    def get_recent_audio(self):
        """
        stt_core.py에서 GCP STT 검증을 위해 호출
        중요: 내부 버퍼는 float32이지만, GCP STT 모듈은 int16 bytes를 기대함.
        여기서 변환해서 반환해야 함.
        """
        if self.recent_detected_audio is None:
            return b""
        
        # Float32 (-1.0 ~ 1.0) -> Int16 (-32768 ~ 32767) 변환
        audio_float = self.recent_detected_audio
        audio_int16 = (audio_float * 32768.0).clip(-32768, 32767).astype(np.int16)
        
        # 사용 후 비우기
        self.recent_detected_audio = None
        
        return audio_int16.tobytes()
    
    def clear_events(self):
        """wakeword 감지 버퍼 완전 초기화"""
        # detect_queue 비우기
        while not self.detect_queue.empty():
            try:
                self.detect_queue.get_nowait()
            except Exception:
                break

# -----------------------------
# 테스트
# -----------------------------

if __name__ == "__main__":
    import sounddevice as sd # 테스트에서만 사용
    
    detector = WakewordDetector("/home/pi/wakeword_onair_mfcc_fp16.tflite")
    detector.start()

    print("🎙️ 'onAir' 라고 말하세요...")

    try:
        with sd.InputStream(
            channels=1,
            samplerate=SAMPLE_RATE,
            blocksize=512,
            dtype='float32',
            callback=lambda indata, frames, time_info, status:
                detector.process_audio_chunk(indata)
        ):
            while True:
                if detector.wait_for_wakeword(timeout=0.5):
                    print("✅ wakeword detected!")

    except KeyboardInterrupt:
        detector.stop()
        print("종료합니다.")