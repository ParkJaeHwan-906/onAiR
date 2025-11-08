"""
Wakeword 감지 모듈 (라즈베리파이용)
Google Voice HAT + Python 3.10 + TFLite int8 모델 버전
"""
import threading
import queue
import sounddevice as sd
import numpy as np
import scipy.signal
import tflite_runtime.interpreter as tflite
from collections import deque
import time
import os

SAMPLE_RATE = 16000
DURATION = 1.0
N_FFT = 400
HOP_LENGTH = 160
N_MELS = 40
WAKEWORD_THRESHOLD = 0.95
LABELS = ["onair", "negative"]

# -----------------------------
# Mel 필터 계산
# -----------------------------
def hz_to_mel(hz): return 2595 * np.log10(1 + hz / 700.0)
def mel_to_hz(mel): return 700 * (10**(mel / 2595.0) - 1)

def mel_filterbank(n_mels=N_MELS, n_fft=N_FFT, sr=SAMPLE_RATE, fmin=0, fmax=None):
    fmax = fmax or sr / 2
    mel_points = np.linspace(hz_to_mel(fmin), hz_to_mel(fmax), n_mels + 2)
    hz_points = mel_to_hz(mel_points)
    bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)
    fbanks = np.zeros((n_mels, n_fft // 2 + 1))
    for i in range(1, n_mels + 1):
        left, center, right = bin_points[i - 1], bin_points[i], bin_points[i + 1]
        for j in range(left, center):
            fbanks[i - 1, j] = (j - left) / (center - left)
        for j in range(center, right):
            fbanks[i - 1, j] = (right - j) / (right - center)
    return fbanks

MEL_FB = mel_filterbank()

# -----------------------------
# WakewordDetector 클래스
# -----------------------------
class WakewordDetector:
    def __init__(self, model_path="/home/pi/wakeword_onair_cnn.tflite"):
        self.model_path = model_path
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.detection_queue = queue.Queue()
        self.is_running = False
        self.thread = None
        self._load_model()

    def _load_model(self):
        """TFLite 모델 로드"""
        try:
            self.interpreter = tflite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()[0]
            self.output_details = self.interpreter.get_output_details()[0]
            print(f"✅ Wakeword 모델 로드 완료: {self.model_path}")
        except Exception as e:
            print(f"⚠️ Wakeword 모델 로드 실패: {e}")
            self.interpreter = None

    def extract_features(self, audio):
        """오디오 → Mel Spectrogram 변환"""
        _, _, Zxx = scipy.signal.stft(
            audio, fs=SAMPLE_RATE, window="hann",
            nperseg=N_FFT, noverlap=N_FFT - HOP_LENGTH
        )
        power = np.abs(Zxx) ** 2
        power = power / np.sum(np.hanning(N_FFT)**2)
        mel = np.dot(MEL_FB, power)
        mel_norm = mel / (np.max(mel) + 1e-6)
        mel_db = 10 * np.log10(mel_norm + 1e-10)
        mel_db = np.clip(mel_db, -80, 0)
        mel_db = mel_db.T
        mel_db = np.pad(mel_db, ((0, max(0, 98 - mel_db.shape[0])), (0, 0)))[:98, :]
        return np.expand_dims(mel_db, (0, -1)).astype(np.float32)

    def predict_wakeword(self, audio_chunk):
        """TFLite 모델 예측"""
        if self.interpreter is None:
            return None
        features = self.extract_features(audio_chunk)
        self.interpreter.set_tensor(self.input_details["index"], features)
        self.interpreter.invoke()
        pred = self.interpreter.get_tensor(self.output_details["index"])[0]
        return pred

    def _detection_loop(self):
        """Wakeword 감지 루프 (별도 스레드에서 실행)"""
        buffer = deque(maxlen=int(SAMPLE_RATE * DURATION))

        def callback(indata, frames, time_info, status):
            buffer.extend(indata[:, 0])
            if len(buffer) >= SAMPLE_RATE:
                audio = np.array(buffer)
                pred = self.predict_wakeword(audio)
                if pred is not None:
                    label = "onair" if np.argmax(pred) == 0 else "negative"
                    conf = np.max(pred)
                    if label == "onair" and conf > WAKEWORD_THRESHOLD:
                        print(f"🚀 Wakeword 감지됨! (신뢰도: {conf*100:.1f}%)")
                        self.detection_queue.put(True)
                        buffer.clear()
                        time.sleep(1.0)  # 중복 방지

        try:
            with sd.InputStream(
                callback=callback,
                channels=1,
                samplerate=SAMPLE_RATE,
                device="hw:CARD=sndrpigooglevoi,DEV=0"  # 명시적 장치 지정
            ):
                print("🎧 Wakeword 감지 대기 중... (onAir)")
                while self.is_running:
                    time.sleep(0.1)
        except Exception as e:
            print(f"❌ Wakeword 감지 오류: {e}")

    def start(self):
        """Wakeword 감지 시작"""
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.thread.start()
        print("✅ Wakeword 감지기 시작")

    def stop(self):
        """Wakeword 감지 중지"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("🔇 Wakeword 감지기 중지")

    def wait_for_wakeword(self, timeout=None):
        """Wakeword 감지 대기"""
        try:
            if self.interpreter is None:
                print("🎧 [더미] Wakeword 감지 대기 중... (즉시 통과)")
                return True
            detected = self.detection_queue.get(timeout=timeout)
            return detected
        except queue.Empty:
            return False


# -----------------------------
# 단독 테스트 실행
# -----------------------------
if __name__ == "__main__":
    detector = WakewordDetector("/home/pi/wakeword_onair_cnn.tflite")
    detector.start()
    print("🎙️ 'onAir'라고 말해보세요! 감지 중입니다...")
    try:
        while True:
            if detector.wait_for_wakeword(timeout=1.0):
                print("✅ Wakeword 감지됨 → 후속 동작 트리거 가능")
    except KeyboardInterrupt:
        detector.stop()
        print("🛑 종료되었습니다.")
