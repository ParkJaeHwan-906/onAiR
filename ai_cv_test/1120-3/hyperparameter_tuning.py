from ultralytics import YOLO
import optuna
from optuna.trial import TrialState
import os


DATA_PATH = "data.yaml"
MODEL_PATH = "yolo11n.pt"
PROJECT_PATH = "runs/tune_optuna"
N_TRIALS = 10
EPOCHS = 30
DEVICE = 1 
IMG_SIZE = (480,360)


def objective(trial):
    lr0 = trial.suggest_float("lr0", 1e-4, 1e-2, log=True)
    momentum = trial.suggest_float("momentum", 0.90, 0.97)
    weight_decay = trial.suggest_float("weight_decay", 1e-5, 1e-3, log=True)
    dropout = trial.suggest_float("dropout", 0.0, 0.1)
    translate = trial.suggest_float("translate", 0.0, 0.3)
    scale = trial.suggest_float("scale", 0.3, 0.6)
    hsv_v = trial.suggest_float("hsv_v", 0.3, 0.6)
    optimizer = trial.suggest_categorical("optimizer", ["SGD", "AdamW"])

    model = YOLO(MODEL_PATH)

    results = model.train(
        data=DATA_PATH,
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=8,
        device=DEVICE,
        project=PROJECT_PATH,
        name=f"trial_{trial.number}",
        lr0=lr0,
        momentum=momentum,
        weight_decay=weight_decay,
        dropout=dropout,
        translate=translate,
        scale=scale,
        hsv_v=hsv_v,
        optimizer=optimizer,
        pretrained=True,
        cos_lr=True,
        multi_scale=True,
        seed=42,
        verbose=False
    )

    metrics = model.val()
    score = metrics.box.map50
    return score


study = optuna.create_study(
    direction="maximize",
    study_name="YOLOv11n_Optuna_Tuning"
)
study.optimize(objective, n_trials=N_TRIALS, timeout=None)


print("\n=== 최적 하이퍼파라미터 ===")
for key, value in study.best_params.items():
    print(f"{key}: {value}")

print(f"\n Best mAP@50: {study.best_value:.4f}")

os.makedirs(PROJECT_PATH, exist_ok=True)
study.trials_dataframe().to_csv(os.path.join(PROJECT_PATH, "optuna_results.csv"), index=False)


try:
    import optuna.visualization as vis
    vis.plot_optimization_history(study).write_html(os.path.join(PROJECT_PATH, "optuna_history.html"))
    vis.plot_param_importances(study).write_html(os.path.join(PROJECT_PATH, "optuna_importance.html"))
    print("\n 시각화 HTML 저장 완료 (optuna_history.html, optuna_importance.html)")
except:
    print("시각화 모듈(optuna.visualization) 불가 시 무시됨.")
