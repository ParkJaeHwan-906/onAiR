import os
import random
import shutil


TRAIN_IMG_DIR = os.path.join("train", "images")
VALID_IMG_DIR = os.path.join("valid", "images")

CALIB_DIR = "calib"
CALIB_COUNT = 120   # calibration 이미지 수 (조절 가능)

os.makedirs(CALIB_DIR, exist_ok=True)

# 이미지 리스트 수집
all_images = []
for d in [TRAIN_IMG_DIR, VALID_IMG_DIR]:
    for f in os.listdir(d):
        if f.lower().endswith((".jpg", ".png", ".jpeg")):
            all_images.append(os.path.join(d, f))

print(f"총 {len(all_images)}장 중 {CALIB_COUNT}장 추출")

# 랜덤 샘플링
sample_imgs = random.sample(all_images, CALIB_COUNT)

# 복사
for img in sample_imgs:
    shutil.copy(img, CALIB_DIR)

print(f"[완료] Calibration 폴더 생성 → {CALIB_DIR}")
