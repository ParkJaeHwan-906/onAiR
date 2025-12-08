from ultralytics import YOLO
import torch
import os

# 모델 경로 (절대경로 권장)
model_path = "/home/j-k13a407/object-detection-4/runs/final_train/hvac_yolo11n_final/weights/best.pt"

# 테스트할 영상 경로
video_path = "/home/j-k13a407/KakaoTalk_20251028_141656357_rotated.mp4"

# 저장 경로 설정
save_dir = "/home/j-k13a407/runs/detect/video_test"

device = 1 if torch.cuda.is_available() else "cpu"
print(f"🧠 Using device: {device}")

model = YOLO(model_path)

results = model.predict(
    source=video_path,        # 🎥 입력 영상 경로
    conf=0.4,                 # 탐지 confidence threshold
    iou=0.45,                 # NMS IoU threshold
    save=True,                # 결과 영상 저장
    save_txt=False,           # 라벨 txt 저장 여부
    show=False,               # 창 띄우기 (True 가능)
    project=save_dir,         # 저장 폴더
    name="",                  # 세션명 (빈칸이면 자동 생성)
    device=device,            # GPU/CPU 선택
    stream=False              # 전체 영상 처리
)


print("✅ 영상 탐지 완료!")

# results[0]에는 첫 결과 객체
output_dir = results[0].save_dir if hasattr(results[0], "save_dir") else save_dir
print("📁 결과 영상 저장 위치:", output_dir)

# FPS 및 속도 정보 출력
if hasattr(results[0], "speed"):
    print("⚡ 속도 (ms/frame):", results[0].speed)
