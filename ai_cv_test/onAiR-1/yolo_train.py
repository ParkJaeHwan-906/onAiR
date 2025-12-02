from ultralytics import YOLO

model = YOLO("yolo11n.pt")

DATA_PATH = "data.yaml"

# Optuna 튜닝 결과(best_params):
best_params = {
    "lr0": 0.0010740214457730327,
    "weight_decay": 0.00012281550171450544,
    "hsv_v": 0.24255139599293166,
    "translate": 0.1523117532627592,
    "scale": 0.7822945024231999,
    "optimizer": "AdamW",
}

model.train(
    data=DATA_PATH,
    epochs=100,
    imgsz=(480, 360),
    batch=8,
    device=1,
    workers=16,

    pretrained=True,
    optimizer=best_params["optimizer"],
    lr0=best_params["lr0"],
    weight_decay=best_params["weight_decay"],

    hsv_h=0.01,
    hsv_s=0.3,
    hsv_v=best_params["hsv_v"],

    translate=best_params["translate"],
    scale=best_params["scale"],

    mosaic=0.2,
    mixup=0.0,
    copy_paste=0.0,

    patience=50,
    cache=True,
)
