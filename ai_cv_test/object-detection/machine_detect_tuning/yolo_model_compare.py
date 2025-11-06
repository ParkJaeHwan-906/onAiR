"""
HVAC Equipment Detection Performance Improvement Pipeline
---------------------------------------------------------
자동으로 YOLOv11n/s/m 모델 학습 → 성능 비교 그래프 생성
"""

import os
from ultralytics import YOLO
import matplotlib.pyplot as plt
import json

DATA_PATH = "object-detection-3/data.yaml"
PROJECT_PATH = "object-detection-3/runs/compare_models"
EPOCHS = 100
IMG_SIZE = 640
DEVICE = 1
MODELS = ["yolo11n.pt", "yolo11s.pt", "yolo11m.pt"]

os.makedirs(PROJECT_PATH, exist_ok=True)

results_summary = {}


# 각 모델 학습 및 성능 저장
for model_name in MODELS:
    exp_name = f"hvac_{model_name.split('.')[0]}"
    print(f"\n Training {model_name}...\n")

    model = YOLO(model_name)

    # 학습
    results = model.train(
        data=DATA_PATH,
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=16,
        device=DEVICE,
        project=PROJECT_PATH,
        name=exp_name,
        pretrained=True,
        multi_scale=True,
        freeze=10
    )

    # 검증
    metrics = model.val(data=DATA_PATH)
    results_summary[model_name] = {
        "mAP50": metrics.box.map50,
        "mAP5095": metrics.box.map,
        "Precision": metrics.box.mp,
        "Recall": metrics.box.mr
    }

    # 로그 저장
    with open(os.path.join(PROJECT_PATH, f"{exp_name}_metrics.json"), "w") as f:
        json.dump(results_summary[model_name], f, indent=4)


# 결과 비교 그래프 출력

names = list(results_summary.keys())
mAP50 = [results_summary[m]["mAP50"] for m in names]
mAP5095 = [results_summary[m]["mAP5095"] for m in names]
precisions = [results_summary[m]["Precision"] for m in names]
recalls = [results_summary[m]["Recall"] for m in names]

plt.figure(figsize=(10, 6))
x = range(len(names))
plt.plot(x, mAP50, marker='o', label='mAP@50')
plt.plot(x, mAP5095, marker='o', label='mAP@50–95')
plt.plot(x, precisions, marker='o', label='Precision')
plt.plot(x, recalls, marker='o', label='Recall')

plt.xticks(x, names)
plt.title("YOLOv11 Model Performance Comparison")
plt.xlabel("Model")
plt.ylabel("Score")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(PROJECT_PATH, "comparison_results.png"))
plt.show()


# 최고 성능 모델 찾기

best_model = max(results_summary.items(), key=lambda x: x[1]["mAP50"])
print(f"\n Best model: {best_model[0]} (mAP@50={best_model[1]['mAP50']:.3f})")

# 요약 저장
with open(os.path.join(PROJECT_PATH, "summary.json"), "w") as f:
    json.dump(results_summary, f, indent=4)

print("\n Performance summary saved to:", PROJECT_PATH)
