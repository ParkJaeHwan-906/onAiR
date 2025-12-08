from ultralytics import YOLO

DATA_PATH = "data.yaml"
MODEL_PATH = "yolo11n.pt"

BEST_PARAMS = {
    "lr0": 0.0005096182289932667,
    "weight_decay": 1.0557769337249535e-05,
    "hsv_v": 0.11011697783052958,
    "translate": 0.14531823022661994,
    "scale": 0.7709914837641928,
    "optimizer": "AdamW"
}

model = YOLO(MODEL_PATH)

model.train(
    data=DATA_PATH,
    epochs=200,
    imgsz=(480,360),
    batch=8,
    device=1,
    pretrained=True,
    project="runs/final_train",
    name="yolo11_final",

    lr0=BEST_PARAMS["lr0"],
    weight_decay=BEST_PARAMS["weight_decay"],
    hsv_v=BEST_PARAMS["hsv_v"],
    translate=BEST_PARAMS["translate"],
    scale=BEST_PARAMS["scale"],
    optimizer=BEST_PARAMS["optimizer"],

    cos_lr=True,
    multi_scale=True,
    seed=42,
    verbose=True,
)
