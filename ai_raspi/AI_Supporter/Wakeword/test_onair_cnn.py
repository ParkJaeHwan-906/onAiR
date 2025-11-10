import os
import tensorflow as tf
import numpy as np
import librosa

MODEL_PATH = "wakeword_onair_cnn.tflite"
LABELS = ["onair", "negative"]
SAMPLE_RATE = 16000
DURATION = 1.0
N_MELS = 40


def preprocess_audio(path):
    wav, _ = librosa.load(path, sr=SAMPLE_RATE)
    target_len = int(SAMPLE_RATE * DURATION)
    if len(wav) < target_len:
        wav = np.pad(wav, (0, target_len - len(wav)))
    else:
        wav = wav[:target_len]
    mel = librosa.feature.melspectrogram(
        y=wav, sr=SAMPLE_RATE, n_fft=400, hop_length=160, n_mels=N_MELS
    )
    mel_db = librosa.power_to_db(mel, ref=np.max).T
    mel_db = np.pad(mel_db, ((0, max(0, 98 - mel_db.shape[0])), (0, 0)))[:98, :]
    mel_db = np.expand_dims(mel_db, axis=(0, -1))  # (1, 98, 40, 1)
    return mel_db


if MODEL_PATH.endswith(".keras"):
    model = tf.keras.models.load_model(MODEL_PATH)
    def predict_audio(path):
        x = preprocess_audio(path)
        pred = model.predict(x, verbose=0)[0]
        label = LABELS[np.argmax(pred)]
        print(f"🎧 {os.path.basename(path)} → {label} ({pred.max()*100:.2f}%)")

elif MODEL_PATH.endswith(".tflite"):
    interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    def predict_audio(path):
        x = preprocess_audio(path).astype(np.float32)
        interpreter.set_tensor(input_details['index'], x)
        interpreter.invoke()
        pred = interpreter.get_tensor(output_details['index'])[0]
        label = LABELS[np.argmax(pred)]
        print(f"🎧 {os.path.basename(path)} → {label} ({pred.max()*100:.2f}%)")

else:
    raise ValueError("지원하지 않는 모델 형식입니다 (.keras or .tflite)")

TEST_DIR = "onair_test"
for f in os.listdir(TEST_DIR):
    if f.endswith(".wav"):
        predict_audio(os.path.join(TEST_DIR, f))
