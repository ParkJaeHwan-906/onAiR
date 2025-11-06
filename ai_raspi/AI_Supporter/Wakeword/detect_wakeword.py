import sounddevice as sd
import numpy as np
import tensorflow as tf
import librosa
from collections import deque
import time

SAMPLE_RATE = 16000
DURATION = 1.0  # 1초 창
N_MELS = 40

interpreter = tf.lite.Interpreter(model_path="wakeword_onair_cnn.tflite")
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()[0]
output_details = interpreter.get_output_details()[0]

def extract_features(audio):
    mel = librosa.feature.melspectrogram(
        y=audio, sr=SAMPLE_RATE, n_fft=400, hop_length=160, n_mels=N_MELS
    )
    mel_db = librosa.power_to_db(mel, ref=np.max).T
    mel_db = np.pad(mel_db, ((0, max(0, 98 - mel_db.shape[0])), (0, 0)))[:98, :]
    mel_db = np.expand_dims(mel_db, (0, -1)).astype(np.float32)
    return mel_db

def predict_wakeword(audio_chunk):
    features = extract_features(audio_chunk)
    interpreter.set_tensor(input_details['index'], features)
    interpreter.invoke()
    pred = interpreter.get_tensor(output_details['index'])[0]
    return pred

buffer = deque(maxlen=int(SAMPLE_RATE * DURATION))

last_print_time = 0
def callback(indata, frames, time_info, status):
    global last_print_time
    buffer.extend(indata[:, 0])

    # 실시간 입력 레벨 표시 (0.5초 간격)
    if time.time() - last_print_time > 0.5:
        rms = np.sqrt(np.mean(np.square(indata)))
        db = 20 * np.log10(rms + 1e-6)
        level_bar = "#" * int((db + 60) / 4)  # -60~0dB 구간 시각화
        print(f"\r🎧 Input Level: {db:6.1f} dB {level_bar:<15}", end="")
        last_print_time = time.time()

    # Wakeword 감지
    if len(buffer) >= SAMPLE_RATE:
        audio = np.array(buffer)
        pred = predict_wakeword(audio)
        label = "onair" if np.argmax(pred) == 0 else "negative"
        conf = np.max(pred)

        # 디버그 출력
        print(f"\nlabel={label}, conf={conf:.2f}")

        if label == "onair" and conf > 0.75:
            print(f"Wakeword Detected! ({conf*100:.1f}%)")

print("Listening for wakeword 'onair' ... (press Ctrl+C to stop)")
with sd.InputStream(callback=callback, channels=1, samplerate=SAMPLE_RATE):
    while True:
        pass
