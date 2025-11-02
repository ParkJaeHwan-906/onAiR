import os
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

import numpy as np
import tensorflow as tf
import librosa
from microwakeword.layers import sub_spectral_normalization
import microwakeword.layers.strided_drop as strided_drop

# === Custom Layers 등록 (직렬화 호환용) ===
tf.keras.utils.get_custom_objects().update({
    "SubSpectralNormalization": sub_spectral_normalization.SubSpectralNormalization,
    "StridedDropout": strided_drop.StridedDropout
})

# === 모델 로드 ===
model = tf.keras.models.load_model("wakeword_onair_model.keras", safe_mode=False)
print("✅ Model loaded successfully")

# === 오디오 파일 경로 지정 ===
audio_path = "data/onair/onair_0000.wav"  # 테스트할 파일 이름 (경로 맞게 수정)

# === 파라미터 ===
sr = 16000
duration = 1.0
n_mels = 40
frame_length = 400
frame_step = 160

# === 오디오 로드 및 전처리 ===
wav, _ = librosa.load(audio_path, sr=sr)
target_len = int(sr * duration)
if len(wav) < target_len:
    wav = np.pad(wav, (0, target_len - len(wav)))
else:
    wav = wav[:target_len]

# === Mel Spectrogram ===
mel = librosa.feature.melspectrogram(y=wav, sr=sr, n_fft=frame_length, hop_length=frame_step, n_mels=n_mels)
mel_db = librosa.power_to_db(mel, ref=np.max).T  # (time, mel)

# (98, 40) 고정
if mel_db.shape[0] > 98:
    mel_db = mel_db[:98, :]
elif mel_db.shape[0] < 98:
    mel_db = np.pad(mel_db, ((0, 98 - mel_db.shape[0]), (0, 0)))

# (1, 98, 40, 1)
input_data = np.expand_dims(mel_db, axis=(0, -1))

# === 예측 ===
pred = model.predict(input_data)
pred_class = np.argmax(pred, axis=1)[0]
confidence = np.max(pred)

# === 결과 출력 ===
labels = ["onair", "negative"]
print(f"🎤 Predicted: {labels[pred_class]} (confidence: {confidence:.3f})")
