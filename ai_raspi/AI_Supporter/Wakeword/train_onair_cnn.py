import os
import numpy as np
import tensorflow as tf
import librosa
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical

SAMPLE_RATE = 16000
DURATION = 1.0
N_MELS = 40
LABELS = ["onair", "negative"]

def load_audio_dataset(base_dir, labels):
    X, y = [], []
    for label_idx, label in enumerate(labels):
        label_dir = os.path.join(base_dir, label)
        for file in os.listdir(label_dir):
            if file.endswith(".wav"):
                path = os.path.join(label_dir, file)
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
                X.append(mel_db)
                y.append(label_idx)
    X = np.expand_dims(np.array(X), -1)
    y = to_categorical(np.array(y), num_classes=len(labels))
    return X, y


print("🎧 Loading dataset...")
X, y = load_audio_dataset("data", LABELS)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"✅ Data loaded: {X.shape}, Labels: {LABELS}")

def build_cnn_model(input_shape=(98, 40, 1), num_classes=2):
    inputs = tf.keras.Input(shape=input_shape)

    x = tf.keras.layers.Conv2D(32, (3, 3), padding="same", activation="relu")(inputs)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.MaxPooling2D((2, 2))(x)

    x = tf.keras.layers.Conv2D(64, (3, 3), padding="same", activation="relu")(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.MaxPooling2D((2, 2))(x)

    x = tf.keras.layers.Conv2D(128, (3, 3), padding="same", activation="relu")(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)

    x = tf.keras.layers.Dropout(0.3)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax")(x)

    model = tf.keras.Model(inputs, outputs)
    return model


model = build_cnn_model()
model.compile(
    optimizer=tf.keras.optimizers.Adam(1e-4),
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)
model.summary()

print("🚀 Training start...")
history = model.fit(
    X_train, y_train,
    validation_data=(X_test, y_test),
    epochs=30,
    batch_size=32,
    verbose=1
)

loss, acc = model.evaluate(X_test, y_test, verbose=0)
print(f"Test Accuracy: {acc:.4f}, Loss: {loss:.4f}")

model.save("wakeword_onair_cnn.keras")
print("Model saved as wakeword_onair_cnn.keras")

converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()
open("wakeword_onair_cnn.tflite", "wb").write(tflite_model)
print("TFLite model exported as wakeword_onair_cnn.tflite")
