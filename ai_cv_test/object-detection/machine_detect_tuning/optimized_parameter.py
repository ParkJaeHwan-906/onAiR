from ultralytics import YOLO

model = YOLO("yolo11n.pt")

results = model.train(
    data="object-detection-4/data.yaml",
    epochs=120,
    imgsz=512,
    batch=8,
    device=1,
    project="object-detection-4/runs/final_train",
    name="hvac_yolo11n_final",
    pretrained=True,
    optimizer="AdamW",
    lr0=0.00599,
    momentum=0.9586,
    weight_decay=0.0002399,
    dropout=0.022,
    translate=0.025,
    scale=0.448,
    hsv_v=0.54,
    cos_lr=True,
    multi_scale=True,
    seed=42
)

metrics = model.val(conf=0.4, iou=0.45)
print(metrics.box.map50, metrics.box.map, metrics.speed)
