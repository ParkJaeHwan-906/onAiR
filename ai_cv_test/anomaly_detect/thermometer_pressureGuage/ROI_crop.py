
import cv2
from ultralytics import YOLO
import os

# YOLO 모델 로드
model = YOLO("all.pt")

def save_roi(img, box, out_dir="roi_debug"):
    os.makedirs(out_dir, exist_ok=True)
    x1, y1, x2, y2 = map(int, box)
    crop = img[y1:y2, x1:x2]
    cv2.imwrite(f"{out_dir}/roi_{x1}_{y1}.png", crop)
    return crop

def detect_and_crop_gauge(image_path, conf_thres=0.5):
    img = cv2.imread(image_path)
    if img is None:
        print("이미지 로드 실패")
        return []

    results = model(img)[0]
    rois = []

    for box in results.boxes:
        cls = results.names[int(box.cls)]
        if cls not in ["pressure_gauge", "thermometer", "gauge"]:
            continue

        if float(box.conf) < conf_thres:
            continue

        x1, y1, x2, y2 = box.xyxy[0]
        roi = save_roi(img, (x1, y1, x2, y2))
        rois.append((cls, roi))

    return rois



if __name__ == "__main__":
    rois = detect_and_crop_gauge("pres5.jpeg")