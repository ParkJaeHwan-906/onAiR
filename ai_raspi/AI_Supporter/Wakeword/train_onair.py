# ============================================
# 🧠 Wakeword ("onair") Detection Model Training
# Env: conda env 'micwow' (TF 2.x + microwakeword)
# ============================================

# ---- GPU 고정 (TF import 전에 설정해야 함) ----
import os
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

# ---- 이후 임포트 ----
import tensorflow as tf
import numpy as np
import librosa
import uuid
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.layers import Lambda, Conv2D, BatchNormalization, ReLU

# ---- microwakeword 관련 ----
from microwakeword import inception
from microwakeword.layers import stream, sub_spectral_normalization
import microwakeword.layers.strided_drop as strided_drop

# ---- 커스텀 레이어 등록 (로드 시 오류 방지) ----
tf.keras.utils.get_custom_objects().update({
    "SubSpectralNormalization": sub_spectral_normalization.SubSpectralNormalization,
    "StridedDropout": strided_drop.StridedDropout,
})

# Stream 클래스 누락 대비
if not hasattr(stream, "Stream"):
    class DummyStream:
        def __init__(self, *args, **kwargs): pass
        def __call__(self, inputs): return inputs
    stream.Stream = DummyStream

# StridedDrop 네이밍 보정
if not hasattr(strided_drop, "StridedDrop"):
    strided_drop.StridedDrop = strided_drop.StridedDropout


# ============================================
# 🔹 conv2d_bn 안전 버전 (기능 동일, 에러만 제거)
#    - 원래 동작 그대로: 5D → squeeze(2) → squeeze(-1) → expand_dims(-1)
#    - 유니크 네이밍 + output_shape 명시만 추가
# ============================================
def _conv2d_bn_safe(x, filters, kernel_size, dilation=(1, 1), subgroups=1, **kwargs):
    tf.keras.backend.set_image_data_format("channels_last")

    rank = getattr(x.shape, "rank", len(x.shape))

    if rank == 5:
        # (B, H, 1, W, 1) --squeeze axis=2--> (B, H, W, 1)
        name1 = f"squeeze_ax2_{uuid.uuid4().hex[:8]}"
        x = Lambda(
            lambda t: tf.squeeze(t, axis=2),
            output_shape=lambda s: (s[0], s[1], s[3], s[4]),
            name=name1
        )(x)

        # (B, H, W, 1) --squeeze axis=-1--> (B, H, W)
        name2 = f"squeeze_last_{uuid.uuid4().hex[:8]}"
        x = Lambda(
            lambda t: tf.squeeze(t, axis=-1),
            output_shape=lambda s: (s[0], s[1], s[2]),
            name=name2
        )(x)

        # (B, H, W) --expand_dims axis=-1--> (B, H, W, 1)
        name3 = f"expand_ch_{uuid.uuid4().hex[:8]}"
        x = Lambda(
            lambda t: tf.expand_dims(t, axis=-1),
            output_shape=lambda s: (s[0], s[1], s[2], 1),
            name=name3
        )(x)

    elif rank == 4:
        # (B, H, W, C) 그대로 사용
        pass

    elif rank == 3:
        # (B, H, W) → (B, H, W, 1)
        name4 = f"expand3to4_{uuid.uuid4().hex[:8]}"
        x = Lambda(
            lambda t: tf.expand_dims(t, axis=-1),
            output_shape=lambda s: (s[0], s[1], s[2], 1),
            name=name4
        )(x)

    else:
        raise ValueError(f"Unexpected input rank for conv2d_bn_safe: {rank}")

    # Conv2D 수행 (원래 파이프라인 그대로)
    x = Conv2D(
        filters=filters,
        kernel_size=kernel_size,
        padding="valid",
        dilation_rate=dilation,
        groups=subgroups,
        use_bias=False,
    )(x)
    x = BatchNormalization()(x)
    x = ReLU()(x)
    return x

# inception 내부 conv2d_bn 교체
inception.conv2d_bn = _conv2d_bn_safe


# ============================================
# 🔹 설정값 (Flags 클래스) — 기존 그대로
# ============================================
class Flags:
    def __init__(self):
        self.num_classes = 2
        self.dropout = 0.3
        self.learning_rate = 1e-4
        self.optimizer = "adam"
        self.momentum = 0.9
        self.use_batch_norm = True

        self.cnn1_filters = "32"
        self.cnn2_filters = "64"
        self.cnn3_filters = "128"
        self.cnn4_filters = "256"

        self.cnn1_kernel_sizes = "(3, 3)"
        self.cnn2_kernel_sizes = "(3, 3)"
        self.cnn3_kernel_sizes = "(3, 3)"
        self.cnn4_kernel_sizes = "(3, 3)"

        self.cnn1_subspectral_groups = "1"
        self.cnn2_subspectral_groups = "1"
        self.cnn3_subspectral_groups = "1"
        self.cnn4_subspectral_groups = "1"

        self.cnn2_filters1 = "64"
        self.cnn2_filters2 = "64"
        self.cnn2_filters3 = "64"
        self.cnn3_filters1 = "128"
        self.cnn3_filters2 = "128"
        self.cnn3_filters3 = "128"
        self.cnn4_filters1 = "256"
        self.cnn4_filters2 = "256"
        self.cnn4_filters3 = "256"

        self.cnn2_kernel_sizes1 = "(3,3)"
        self.cnn2_kernel_sizes2 = "(5,5)"
        self.cnn2_kernel_sizes3 = "(1,1)"
        self.cnn3_kernel_sizes1 = "(3,3)"
        self.cnn3_kernel_sizes2 = "(5,5)"
        self.cnn3_kernel_sizes3 = "(1,1)"
        self.cnn4_kernel_sizes1 = "(3,3)"
        self.cnn4_kernel_sizes2 = "(5,5)"
        self.cnn4_kernel_sizes3 = "(1,1)"

        self.cnn2_dilation = "(1,1)"
        self.cnn3_dilation = "(1,1)"
        self.cnn4_dilation = "(1,1)"

        self.num_mels = 40
        self.sample_rate = 16000
        self.frame_length = 400
        self.frame_step = 160
        self.feature_type = "mel"

        self.l2_weight_decay = 1e-4
        self.batch_norm_momentum = 0.99

flags = Flags()
flags.streaming = False


# ============================================
# 🔹 모델 구성 (기존 그대로)
# ============================================
input_shape = (98, 40, 1)
batch_size = 32

base_model = inception.model(flags, shape=input_shape, batch_size=batch_size)
x = tf.keras.layers.GlobalAveragePooling2D()(base_model.output)
x = tf.keras.layers.Dropout(flags.dropout)(x)
output = tf.keras.layers.Dense(2, activation="softmax")(x)

model = tf.keras.Model(inputs=base_model.input, outputs=output)

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=flags.learning_rate),
    loss="categorical_crossentropy",
    metrics=["accuracy"],
)

model.summary()


# ============================================
# 🔹 데이터 로딩/전처리 (기존 그대로)
# ============================================
def load_audio_dataset(base_dir, labels, sr=16000, duration=1.0):
    X, y = [], []
    for label_idx, label in enumerate(labels):
        label_dir = os.path.join(base_dir, label)
        for root, _, files in os.walk(label_dir):
            for file in files:
                if file.endswith(".wav"):
                    path = os.path.join(root, file)
                    try:
                        wav, _ = librosa.load(path, sr=sr)
                        target_len = int(sr * duration)
                        if len(wav) < target_len:
                            wav = np.pad(wav, (0, target_len - len(wav)))
                        else:
                            wav = wav[:target_len]

                        mel = librosa.feature.melspectrogram(
                            y=wav, sr=sr, n_fft=400, hop_length=160, n_mels=40
                        )
                        mel_db = librosa.power_to_db(mel, ref=np.max).T

                        if mel_db.shape[0] > 98:
                            mel_db = mel_db[:98, :]
                        elif mel_db.shape[0] < 98:
                            mel_db = np.pad(mel_db, ((0, 98 - mel_db.shape[0]), (0, 0)))

                        X.append(mel_db)
                        y.append(label_idx)
                    except Exception as e:
                        print(f"❌ Error loading {path}: {e}")
    return np.array(X), np.array(y)


labels = ["onair", "negative"]
X, y = load_audio_dataset("data", labels)
X = np.expand_dims(X, -1)  # (N, 98, 40, 1)
y = to_categorical(y, num_classes=2)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)


# ============================================
# 🔹 학습 (기존 그대로)
# ============================================
print("🚀 Training start...")
history = model.fit(
    X_train,
    y_train,
    validation_data=(X_test, y_test),
    batch_size=32,
    epochs=30,
    verbose=1,
)


# ============================================
# 🔹 저장/평가 (기존 그대로)
# ============================================
model.save("wakeword_onair_model.keras", include_optimizer=False)
print("✅ Model saved as wakeword_onair_model.keras")

test_loss, test_acc = model.evaluate(X_test, y_test, verbose=0)
print(f"✅ Test Accuracy: {test_acc:.4f}, Loss: {test_loss:.4f}")
