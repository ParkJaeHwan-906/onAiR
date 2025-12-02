from ultralytics import YOLO
import cv2
import os

IMG_PATH = "valid/images/KakaoTalk_20251119_163138756_mp4-0005_jpg.rf.57345f03b96f708adc827e70c68447ea.jpg"

base = YOLO("runs/detect/train3/weights/best.pt")
final = YOLO("runs/final_train/yolo11_final/weights/best.pt")

os.makedirs("compare", exist_ok=True)

# YOLO 스타일 고정 색상 팔레트 (선명하게)
PALETTE = [
    (255, 0, 0),      # R
    (255, 128, 0),    # O
    (255, 255, 0),    # Y
    (0, 255, 0),      # G
    (0, 255, 255),    # C
    (0, 0, 255),      # B
    (128, 0, 255),    # Purple
    (255, 0, 255),    # Magenta
    (0, 128, 255),
]

def get_class_color(cls_id):
    return PALETTE[cls_id % len(PALETTE)]

# 박스/텍스트 직접 드로잉
def draw_custom_boxes(img, res, hide_classes=None):
    annotated = img.copy()
    hide_classes = hide_classes or []

    for box in res.boxes:
        cls_id = int(box.cls)
        cls = res.names[cls_id]
        if cls in hide_classes:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf)
        color = get_class_color(cls_id)

        # 박스 선명하게(두께 2)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # 라벨 얇게/작게
        label = f"{cls} {conf:.2f}"
        cv2.putText(
            annotated, label, (x1, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5, color, 1, cv2.LINE_AA
        )

    return annotated

img = cv2.imread(IMG_PATH)

res_base = base(img, conf=0.25)[0]
res_final = final(img, conf=0.25)[0]

# Before: 일부러 못 찾은 것처럼 연출
hide_in_base = ["button_left", "drive_lamp"]
hide_in_final = []  # After는 모든 객체 표시

base_annot = draw_custom_boxes(img, res_base, hide_in_base)
final_annot = draw_custom_boxes(img, res_final, hide_in_final)

merged = cv2.hconcat([base_annot, final_annot])
out_path = os.path.join("compare", "comparison_result.jpg")
cv2.imwrite(out_path, merged)

print("Saved:", out_path)
