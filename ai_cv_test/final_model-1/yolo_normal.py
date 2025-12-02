from ultralytics import YOLO

model = YOLO("yolo11n.pt")

model.train(
    data="data.yaml",
    epochs=40,          
    imgsz=480,
    device=1,
    pretrained=True,
    optimizer="SGD",    # 기본
    lr0=0.01,           # 기본
    mosaic=1.0,         # 기본
    mixup=0.1,          # 기본
    copy_paste=0.1,     # 기본
)
