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
from scipy.fftpack import dct

SAMPLE_RATE = 16000
DURATION = 2.0  # 버퍼 크기를 2초로 증가 (STT 검증을 위해 더 긴 오디오 필요)
N_FFT = 400
HOP_LENGTH = 160
N_MELS = 40
N_MFCC = 40
WAKEWORD_THRESHOLD = 0.90
LABELS = ["onair", "negative"]
TARGET_FRAMES = 98

# -----------------------------
# Mel 필터 계산
# -----------------------------
def hz_to_mel(hz):
    return 2595 * np.log10(1 + hz / 700.0)

def mel_to_hz(mel):
    return 700 * (10**(mel / 2595.0) - 1)

def build_mel_filterbank(n_mels=N_MELS, n_fft=N_FFT, sr=SAMPLE_RATE):
    fmin = 0
    fmax = sr / 2

    mel_points = np.linspace(hz_to_mel(fmin), hz_to_mel(fmax), n_mels + 2)
    hz_points = mel_to_hz(mel_points)

    bins = np.floor((n_fft + 1) * hz_points / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1))

    for i in range(1, n_mels + 1):
        left = bins[i - 1]
        center = bins[i]
        right = bins[i + 1]

        for j in range(left, center):
            fb[i - 1, j] = (j - left) / (center - left)
        for j in range(center, right):
            fb[i - 1, j] = (right - j) / (right - center)

    return fb

MEL_FBANK = build_mel_filterbank()

def compute_mfcc(audio):
    """librosa 없이 MFCC 계산 (학습과 동일한 형태)"""
    # float32 변환
    wav = audio.astype(np.float32) / 32768.0

    # STFT
    _, _, Zxx = scipy.signal.stft(
        wav,
        fs=SAMPLE_RATE,
        window="hann",
        nperseg=N_FFT,
        noverlap=N_FFT - HOP_LENGTH,
        padded=False,
        boundary=None
    )

    # 파워 스펙트럼
    power = np.abs(Zxx) ** 2

    # Mel Filterbank 적용
    mel_spec = np.dot(MEL_FBANK, power)

    # 로그 적용
    log_mel = np.log10(mel_spec + 1e-10).T  # (time, n_mels)

    # MFCC = DCT(log-mel)
    mfcc = dct(log_mel, type=2, axis=1, norm='ortho')[:, :N_MFCC]

    # 프레임 길이 맞추기
    if mfcc.shape[0] < TARGET_FRAMES:
        mfcc = np.pad(mfcc, ((0, TARGET_FRAMES - mfcc.shape[0]), (0, 0)))
    else:
        mfcc = mfcc[:TARGET_FRAMES]

    # CMVN(정규화)
    mean = np.mean(mfcc)
    std = np.std(mfcc) + 1e-6
    mfcc = (mfcc - mean) / std

    return np.expand_dims(mfcc, (0, -1)).astype(np.float32)
# -----------------------------
# WakewordDetector 클래스
# -----------------------------
class WakewordDetector:
    def __init__(self, model_path="/home/pi/wakeword_onair_cnn.tflite"):
        # model_path가 None이면 기본 경로 사용
        if model_path is None:
            model_path = "/home/pi/wakeword_onair_cnn.tflite"
        self.model_path = model_path
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.detection_queue = queue.Queue()
        self.is_running = False
        self.is_paused = False  # Wakeword 감지 일시 중지 플래그
        self.thread = None
        # 초기화 시 버퍼와 시간 추적 변수 초기화 (첫 번째 wakeword 감지를 위해 필수)
        self.audio_buffer = deque(maxlen=int(SAMPLE_RATE * DURATION))
        self.last_detection_time = 0
        # Wakeword 감지 시점의 오디오를 저장 (STT 검증용)
        self.recent_detected_audio = None
        self._load_model()

    def _load_model(self):
        """TFLite 모델 로드"""
        import os
        try:
            # 파일 존재 여부 확인
            if not os.path.exists(self.model_path):
                print(f"⚠️ Wakeword 모델 파일을 찾을 수 없습니다: {self.model_path}")
                self.interpreter = None
                return
            
            self.interpreter = tflite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()[0]
            self.output_details = self.interpreter.get_output_details()[0]
            print(f"✅ Wakeword 모델 로드 완료: {self.model_path}")
        except Exception as e:
            print(f"⚠️ Wakeword 모델 로드 실패: {e}")
            print(f"   모델 경로: {self.model_path}")
            self.interpreter = None

    def extract_features(self, audio):
        return compute_mfcc(audio)

    def predict_wakeword(self, audio_chunk):
        """TFLite 모델 예측"""
        if self.interpreter is None:
            return None
        features = self.extract_features(audio_chunk)
        self.interpreter.set_tensor(self.input_details["index"], features)
        self.interpreter.invoke()
        pred = self.interpreter.get_tensor(self.output_details["index"])[0]
        return pred

    def process_audio_chunk(self, audio_chunk):
        """
        MicStream에서 받은 오디오 청크를 처리 (16000Hz 기대)
        별도 스트림을 열지 않고 외부에서 오디오 데이터를 받아서 처리
        주의: 이 메서드는 콜백에서 호출되므로 블로킹 작업을 하면 안 됨
        """
        # 디버깅: 첫 호출 시에만 로그 출력 (너무 많은 로그 방지)
        if not hasattr(self, '_first_call_logged'):
            print("✅ Wakeword 콜백 호출됨 (마이크 스트림 정상 작동)")
            self._first_call_logged = True
        
        if self.interpreter is None or not self.is_running or self.is_paused:
            return
        
        # 실제 음성 입력 검증: RMS(루트 평균 제곱) 값으로 볼륨 확인
        # 조용한 환경(노이즈만 있는 경우)에서는 감지하지 않음
        # 주의: audio_chunk는 int16 타입이므로 float32로 변환 시 스케일 유지
        audio_array = np.array(audio_chunk, dtype=np.int16)
        # int16 범위(-32768 ~ 32767)에서 RMS 계산
        rms = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2))
        # RMS 임계값: 너무 조용하면 무시 (실제 음성이 아닌 노이즈로 판단)
        # int16 범위에서 최소 500 이상이어야 실제 음성으로 간주 (노이즈 필터링 강화)
        MIN_RMS_THRESHOLD = 500.0  # int16 범위에서 적절한 값 (기존 100.0 → 500.0으로 상향)
        if rms < MIN_RMS_THRESHOLD:
            return  # 조용한 환경, 실제 음성 없음
        
        # 오디오 데이터를 버퍼에 추가 (1차원 배열로 변환)
        # 주의: audio_buffer와 last_detection_time은 __init__에서 초기화됨
        if isinstance(audio_chunk, np.ndarray):
            if len(audio_chunk.shape) > 1:
                audio_chunk = audio_chunk.flatten()
            self.audio_buffer.extend(audio_chunk)
        
        # 버퍼가 충분히 쌓이면 Wakeword 감지
        # 중복 방지: 최근 3초 이내에 감지했으면 스킵 (기존 1초 → 3초로 연장하여 오탐지 방지)
        current_time = time.time()
        DETECTION_COOLDOWN_SEC = 3.0  # 중복 감지 방지 시간 (초)
        buffer_length = len(self.audio_buffer)
        
        # 버퍼가 최소 길이(0.5초) 이상이고 cooldown이 지났으면 감지 시도
        # 이렇게 하면 짧은 wakeword도 감지 가능 (첫 번째 wakeword 누락 방지)
        # 기존: 1초(16000 샘플) 이상만 감지 → 짧은 wakeword 누락 가능
        # 개선: 0.5초(8000 샘플) 이상이면 감지 → 짧은 wakeword도 감지 가능
        MIN_BUFFER_LENGTH = int(SAMPLE_RATE * 0.5)  # 최소 0.5초 (8000 샘플)
        if buffer_length >= MIN_BUFFER_LENGTH and (current_time - self.last_detection_time) > DETECTION_COOLDOWN_SEC:
            audio = np.array(list(self.audio_buffer))
            
            # 실제 음성 입력 검증: RMS 값으로 볼륨 확인
            # int16 범위에서 RMS 계산 (정확한 스케일 유지)
            audio_int16 = audio.astype(np.int16)
            rms = np.sqrt(np.mean(audio_int16.astype(np.float64) ** 2))
            # RMS 임계값: 너무 조용하면 무시 (실제 음성이 아닌 노이즈로 판단)
            # int16 범위에서 최소 500 이상이어야 실제 음성으로 간주 (노이즈 필터링 강화)
            MIN_RMS_THRESHOLD = 500.0  # int16 범위에서 적절한 값 (기존 100.0 → 500.0으로 상향)
            if rms < MIN_RMS_THRESHOLD:
                # 조용한 환경, 실제 음성 없음 - 버퍼만 비우고 스킵
                self.audio_buffer.clear()
                return
            
            pred = self.predict_wakeword(audio)
            if pred is not None:
                label = "onair" if np.argmax(pred) == 0 else "negative"
                conf = np.max(pred)
                # 디버그: 모든 예측 결과 로깅 (오탐지 원인 파악용)
                if conf > 0.3:  # 임계값 낮춤 (더 많은 로그 확인)
                    print(f"🔍 [Wakeword] 예측: {label}, conf={conf:.3f}, threshold={WAKEWORD_THRESHOLD}, buffer_len={buffer_length}")
                
                if label == "onair" and conf > WAKEWORD_THRESHOLD:
                    print(f"🚀 [Wakeword] 감지됨! (신뢰도: {conf*100:.1f}%)")
                    # 감지 시점의 오디오 버퍼를 저장 (STT 검증용)
                    # 버퍼의 최근 부분만 저장 (이전 대화 내용 제외)
                    # wakeword는 보통 0.5~1초 정도이므로, 최근 1.0초만 저장
                    buffer_list = list(self.audio_buffer)
                    buffer_audio = np.array(buffer_list, dtype=np.int16)
                    buffer_duration = len(buffer_audio) / SAMPLE_RATE
                    
                    # 최근 1.0초만 추출 (wakeword 감지 시점의 오디오만)
                    # 추가로 0.5초를 더 수집하므로, 여기서는 1.0초만 저장
                    EXTRACT_DURATION = 1.0  # 1.0초
                    extract_samples = int(SAMPLE_RATE * EXTRACT_DURATION)
                    if len(buffer_audio) > extract_samples:
                        # 버퍼의 최근 부분만 추출 (뒤에서부터)
                        extracted_audio = buffer_audio[-extract_samples:]
                        extracted_duration = len(extracted_audio) / SAMPLE_RATE
                        print(f"📊 버퍼 전체: {len(buffer_audio)} 샘플 ({buffer_duration:.2f}초) → 최근 {len(extracted_audio)} 샘플 ({extracted_duration:.2f}초)만 저장")
                        self.recent_detected_audio = extracted_audio
                    else:
                        # 버퍼가 짧으면 전체 사용
                        print(f"📊 저장된 오디오: {len(buffer_audio)} 샘플, {buffer_duration:.2f}초 (전체 사용)")
                        self.recent_detected_audio = buffer_audio
                    
                    # 버퍼를 즉시 clear하여 다음 wakeword 감지 시 이전 오디오가 포함되지 않도록 함
                    self.audio_buffer.clear()
                    print(f"🧹 버퍼 clear 완료 (다음 wakeword 감지를 위해)")
                    
                    self.detection_queue.put(True)
                    self.last_detection_time = current_time  # 중복 방지
                elif label == "onair" and conf > 0.7:  # threshold 미만이지만 높은 신뢰도면 경고
                    print(f"⚠️ [Wakeword] 'onair' 예측되었지만 threshold 미만: conf={conf:.3f} < {WAKEWORD_THRESHOLD}")
                    # 버퍼는 유지 (다음 청크와 합쳐서 다시 시도)

    def _detection_loop(self):
        """
        Wakeword 감지 루프 (별도 스레드에서 실행) - 레거시 코드
        주의: 실제로는 MicStream을 통해 process_audio_chunk를 사용하므로 이 메서드는 사용되지 않음
        하지만 start()에서 호출되므로, 오류를 방지하기 위해 더미 모드로만 동작
        """
        # 실제로는 MicStream이 마이크를 열고, 그 콜백을 통해 process_audio_chunk를 호출함
        # 따라서 이 루프는 별도의 마이크 스트림을 열지 않고 더미 모드로만 동작
        # 하드코딩된 장치 이름으로 별도 스트림을 열면 MicStream과 충돌 발생 가능
        print("ℹ️ Wakeword 감지 루프 시작 (더미 모드 - MicStream을 통해 실제 감지 수행)")
        while self.is_running:
            time.sleep(0.1)
        
        # 레거시 코드 (사용 안 함 - 하드코딩된 장치 이름으로 인한 오류 방지)
        # 실제 감지는 MicStream의 콜백을 통해 process_audio_chunk로 수행됨
    
    def start(self):
        """Wakeword 감지 시작"""
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.thread.start()
        print("✅ Wakeword 감지기 시작")

    def pause(self):
        """Wakeword 감지 일시 중지"""
        self.is_paused = True
        # pause 시 버퍼와 시간 추적 변수 초기화 (다음 resume 후 즉시 감지 가능하도록)
        if hasattr(self, 'audio_buffer'):
            self.audio_buffer.clear()
        self.last_detection_time = 0
        print("🔇 Wakeword 감지기 일시 중지")
    
    def resume(self):
        """Wakeword 감지 재개"""
        self.is_paused = False
        # 재개 시 버퍼와 시간 추적 변수 초기화 (즉시 감지 가능하도록)
        if hasattr(self, 'audio_buffer'):
            self.audio_buffer.clear()
        self.last_detection_time = 0  # 재개 시 중복 방지 타이머 리셋
        
        # 큐에 남아있는 값 제거 (이전 감지 신호가 남아있으면 즉시 반환되는 것을 방지)
        while not self.detection_queue.empty():
            try:
                self.detection_queue.get_nowait()
            except queue.Empty:
                break
        
        print("🔊 Wakeword 감지기 재개")
    
    def stop(self):
        """Wakeword 감지 중지"""
        self.is_running = False
        self.is_paused = True
        if self.thread:
            self.thread.join(timeout=2.0)
        print("🔇 Wakeword 감지기 중지")

    # def get_recent_audio(self):
    #     """감지 시점에 저장된 오디오 버퍼를 반환하고 비운다"""
    #     if self.recent_detected_audio is None or len(self.recent_detected_audio) == 0:
    #         # 저장된 오디오가 없으면 현재 버퍼 사용 (fallback)
    #         audio = np.array(list(self.audio_buffer), dtype=np.int16)
    #         self.audio_buffer.clear()
    #     else:
    #         # 저장된 오디오 사용
    #         audio = self.recent_detected_audio.copy()
    #         self.recent_detected_audio = None  # 사용 후 초기화
        
    #     return audio.tobytes()
        

    def get_recent_audio(self):
        """감지 시점에 저장된 오디오 버퍼를 반환하고 비운다"""
        if self.recent_detected_audio is None or len(self.recent_detected_audio) == 0:
            return b""
        audio = self.recent_detected_audio
        self.recent_detected_audio = None 
        return audio.tobytes()

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
    detector = WakewordDetector("/home/pi/Wakeword/wakeword_onair_mfcc_fp16.tflite")
    detector.start()
    print("🎙️ 'onAir'라고 말해보세요! 감지 중입니다...")
    try:
        while True:
            if detector.wait_for_wakeword(timeout=1.0):
                print("✅ Wakeword 감지됨 → 후속 동작 트리거 가능")
    except KeyboardInterrupt:
        detector.stop()
        print("🛑 종료되었습니다.")
