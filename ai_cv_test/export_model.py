from ultralytics import YOLO

model = YOLO("final_v3.pt")
model.export(format="engine", int8=True)