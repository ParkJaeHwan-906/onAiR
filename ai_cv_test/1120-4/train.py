from ultralytics import YOLO

MODEL_PATH = "yolo11n.pt"
DATA_PATH = "data.yaml"

best_params = {
    "lr0": 0.006374464636728678,
    "momentum": 0.9138734595881377,
    "weight_decay": 0.00026651607539504357,
    "dropout": 0.08901722277591374,
    "translate": 0.0072044029626273315,
    "scale": 0.5260757974798587,
    "hsv_v": 0.5566638799458961,
    "optimizer": "SGD"
}

model = YOLO(MODEL_PATH)

model.train(
    data=DATA_PATH,
    epochs=150,  # 정식 학습은 120~200 추천
    imgsz=(480,360),
    batch=8,
    device=1,

    # Best hyperparameters
    lr0=best_params["lr0"],
    momentum=best_params["momentum"],
    weight_decay=best_params["weight_decay"],
    dropout=best_params["dropout"],
    translate=best_params["translate"],
    scale=best_params["scale"],
    hsv_v=best_params["hsv_v"],
    optimizer=best_params["optimizer"],

    pretrained=True,
    cos_lr=True,
    multi_scale=True,
    seed=42,
    
    project="runs/final_train",
    name="best_params_fulltrain"
)