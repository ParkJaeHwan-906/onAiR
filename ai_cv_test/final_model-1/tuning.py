from ultralytics import YOLO
import optuna
import os

DATA_PATH = "data.yaml"
MODEL_PATH = "yolo11n.pt"
PROJECT_PATH = "runs/tune_optuna"

N_TRIALS = 10
EPOCHS = 20
DEVICE = 1
IMG_SIZE = (480, 360)

def objective(trial):
    lr0 = trial.suggest_float("lr0", 1e-4, 3e-3, log=True)
    weight_decay = trial.suggest_float("weight_decay", 1e-5, 1e-3, log=True)
    hsv_v = trial.suggest_float("hsv_v", 0.1, 0.4)
    translate = trial.suggest_float("translate", 0.0, 0.2)
    scale = trial.suggest_float("scale", 0.4, 0.8)
    optimizer = trial.suggest_categorical("optimizer", ["SGD", "AdamW"])

    model = YOLO(MODEL_PATH)

    model.train(
        data=DATA_PATH,
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=8,
        device=DEVICE,
        project=PROJECT_PATH,
        name=f"trial_{trial.number}",
        lr0=lr0,
        weight_decay=weight_decay,
        hsv_v=hsv_v,
        translate=translate,
        scale=scale,
        optimizer=optimizer,
        pretrained=True,
        verbose=False,
        seed=42,
    )

    metrics = model.val()
    return metrics.box.map50

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=N_TRIALS)

print("\n=== Best Hyperparameters ===")
print(study.best_params)
print(f"Best mAP@50: {study.best_value:.4f}")
