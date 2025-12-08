from ultralytics import YOLO
import cv2
from matplotlib import pyplot as plt
import os
import pandas as pd

#학습된 모델 로드
model = YOLO("object-detection-4/runs/final_train/hvac_yolo11n_final/weights/best.pt")

# 테스트 폴더 경로
test_dir = "test/"
output_dir = "object-detection-4/runs/predict_all/"
os.makedirs(output_dir, exist_ok=True)

# 결과 저장용 리스트
results_list = []

# 폴더 내 이미지 전체 순회
for img_name in os.listdir(test_dir):
    if not img_name.lower().endswith((".jpg", ".png", ".jpeg")):
        continue

    img_path = os.path.join(test_dir, img_name)
    print(f"\n Processing: {img_name}")

    # 예측 수행
    results = model.predict(
        source=img_path,
        conf=0.4,
        iou=0.5,
        save=True,
        save_txt=False,
        show=False,
        device=1,
        project=output_dir,
        name="batch_infer"
    )

    # 결과 이미지 출력 (Jupyter 환경일 때만)
    result_image = results[0].plot()
    plt.figure(figsize=(8, 6))
    plt.imshow(cv2.cvtColor(result_image, cv2.COLOR_BGR2RGB))
    plt.axis("off")
    plt.title(f"Detection: {img_name}")
    plt.show()

    # 박스 정보 추출
    boxes = results[0].boxes
    for box in boxes:
        cls = int(box.cls[0])
        conf = float(box.conf[0])
        name = results[0].names[cls]
        results_list.append({
            "image": img_name,
            "class": name,
            "confidence": round(conf, 3)
        })
        print(f"{img_name} → {name} ({conf:.2f})")

# 전체 결과 DataFrame으로 정리
df = pd.DataFrame(results_list)
df_path = os.path.join(output_dir, "prediction_summary.csv")
df.to_csv(df_path, index=False, encoding="utf-8-sig")


print(f"결과 요약 CSV 저장 위치: {df_path}")
print(f"감지 이미지 저장 폴더: {os.path.join(output_dir, 'batch_infer')}")
