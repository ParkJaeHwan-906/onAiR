from ultralytics import YOLO

model = YOLO("yolo11n.pt")

DATA_PATH = "fan-3/data.yaml"

model.train(
    data=DATA_PATH,
    epochs=100,
    imgsz=(480, 360),
    batch=8,
    device=1,
    pretrained=True,
    optimizer="AdamW",
    lr0=0.0006,
    patience=50,

    # ---- Augmentation (Raspberry Pi 환경 최적화) ----
    mosaic=0.2,
    mixup=0.0,
    copy_paste=0.0,
    hsv_h=0.01,
    hsv_s=0.3,
    hsv_v=0.2,

    cache=True,
)
