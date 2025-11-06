from ultralytics import YOLO

model = YOLO("yolo11n.pt")

results = model.train(
    data="control-panel-2/data.yaml",
    epochs=100,
    imgsz=640,
    batch=16,
    device=1,
    workers=8,
    seed=42,
    project="control-panel-2/runs//train",
    name="hvac_yolo11n",
    verbose=True,
    pretrained=True
)

metrics = model.val()
print(metrics)

pred = model.predict(
    source="control-panel-2/test/images",
    save=True,
    conf=0.5
)
