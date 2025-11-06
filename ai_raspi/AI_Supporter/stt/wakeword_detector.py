"""
Wakeword 감지 모듈
별도 스레드에서 실행되어 "onAir" wakeword를 감지합니다.
"""
import threading
import queue
import sounddevice as sd
import numpy as np
import tensorflow as tf
import librosa
from collections import deque
import time
import os

SAMPLE_RATE = 16000
DURATION = 1.0  # 1초 창
N_MELS = 40
WAKEWORD_THRESHOLD = 0.75

class WakewordDetector:
    def __init__(self, model_path=None):
        """
        Wakeword 감지기 초기화
        
        Args:
            model_path: TFLite 모델 경로 (None이면 기본 경로 사용)
        """
        if model_path is None:
            # Wakeword 디렉토리에서 모델 찾기
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(base_dir, "Wakeword", "wakeword_onair_cnn.tflite")
        
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
            self.interpreter = tf.lite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()[0]
            self.output_details = self.interpreter.get_output_details()[0]
            print(f"✅ Wakeword 모델 로드 완료: {self.model_path}")
        except Exception as e:
            print(f"⚠️ Wakeword 모델 로드 실패: {e}")
            print("   더미 모드로 동작합니다 (항상 True 반환)")
            self.interpreter = None
    
    def extract_features(self, audio):
        """오디오에서 특징 추출"""
        mel = librosa.feature.melspectrogram(
            y=audio, sr=SAMPLE_RATE, n_fft=400, hop_length=160, n_mels=N_MELS
        )
        mel_db = librosa.power_to_db(mel, ref=np.max).T
        mel_db = np.pad(mel_db, ((0, max(0, 98 - mel_db.shape[0])), (0, 0)))[:98, :]
        mel_db = np.expand_dims(mel_db, (0, -1)).astype(np.float32)
        return mel_db
    
    def predict_wakeword(self, audio_chunk):
        """Wakeword 예측"""
        if self.interpreter is None:
            return None
        
        features = self.extract_features(audio_chunk)
        self.interpreter.set_tensor(self.input_details['index'], features)
        self.interpreter.invoke()
        pred = self.interpreter.get_tensor(self.output_details['index'])[0]
        return pred
    
    def _detection_loop(self):
        """Wakeword 감지 루프 (별도 스레드에서 실행)"""
        buffer = deque(maxlen=int(SAMPLE_RATE * DURATION))
        
        def callback(indata, frames, time_info, status):
            buffer.extend(indata[:, 0])
            
            # Wakeword 감지
            if len(buffer) >= SAMPLE_RATE:
                audio = np.array(buffer)
                pred = self.predict_wakeword(audio)
                
                if pred is not None:
                    label = "onair" if np.argmax(pred) == 0 else "negative"
                    conf = np.max(pred)
                    
                    if label == "onair" and conf > WAKEWORD_THRESHOLD:
                        print(f"🚀 Wakeword 감지됨! (신뢰도: {conf*100:.1f}%)")
                        self.detection_queue.put(True)
                        # 중복 감지 방지를 위해 버퍼 초기화
                        buffer.clear()
        
        try:
            with sd.InputStream(callback=callback, channels=1, samplerate=SAMPLE_RATE):
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
        """
        Wakeword 감지 대기
        
        Args:
            timeout: 대기 시간 (초), None이면 무한 대기
        
        Returns:
            bool: Wakeword 감지 시 True, timeout 시 False
        """
        try:
            if self.interpreter is None:
                # 더미 모드: 항상 즉시 True 반환
                print("🎧 [더미] Wakeword 감지 대기 중... (현재 즉시 통과)")
                return True
            
            detected = self.detection_queue.get(timeout=timeout)
            return detected
        except queue.Empty:
            return False

