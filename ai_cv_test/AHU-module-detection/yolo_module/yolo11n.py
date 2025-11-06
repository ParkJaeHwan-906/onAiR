from ultralytics import YOLO

model = YOLO("yolo11n.pt")

results = model.train(
    data="../-AHU-module-detection-2/data.yaml",
    epochs=100,
    imgsz=640,
    batch=16,
    device=1,
    workers=8,
    seed=42,
    project="../-AHU-module-detection-2/runs//train",
    name="module_yolo11n",
    verbose=True,
    pretrained=True
)

metrics = model.val()
print(metrics)

pred = model.predict(
    source="../-AHU-module-detection-2/test/images",
    save=True,
    conf=0.5
)
