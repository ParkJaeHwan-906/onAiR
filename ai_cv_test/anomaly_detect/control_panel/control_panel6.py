import cv2
import numpy as np
from ultralytics import YOLO

# ----------------------------
# 빨간 LED 세그먼트 마스크 생성 (개선된 버전)
# ----------------------------
def extract_red_segments(roi):
    # RGB → BGR → 분리
    b, g, r = cv2.split(roi)

    # LED는 r이 가장 높고 g,b보다 확실히 커야 함
    red_strong = (r > 150) & (r > g + 30) & (r > b + 30)
    mask = red_strong.astype(np.uint8) * 255

    # 작은 노이즈 제거
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # LED 굵기 보강
    mask = cv2.dilate(mask, kernel, iterations=1)

    # 업스케일
    mask_big = cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR)
    return mask_big


# ----------------------------
# YOLO로 temperature bbox 추출
# ----------------------------
def get_temperature_roi(model, img):
    results = model(img)[0]

    best_box = None
    best_conf = 0

    for box in results.boxes:
        cls = int(box.cls)
        conf = float(box.conf)

        if model.names[cls] == "temperature" and conf > best_conf:
            best_box = box
            best_conf = conf

    if best_box is None:
        return None

    x1, y1, x2, y2 = map(int, best_box.xyxy[0])
    roi = img[y1:y2, x1:x2]
    return roi


# ----------------------------
# ROI에서 실제 디스플레이 영역만 crop
# ----------------------------
def crop_display_area(roi):
    h, w, _ = roi.shape

    # 더 타이트하게 자르기 (중앙 디스플레이만)
    top = int(h * 0.25)
    bottom = int(h * 0.77)
    left = int(w * 0.22)
    right = int(w * 0.77)

    # 조정 필요시 여기 퍼센트만 수정하면 됨
    disp = roi[top:bottom, left:right]
    return disp


# ----------------------------
# 메인 파이프라인
# ----------------------------
def process_image(img_path, model):
    img = cv2.imread(img_path)

    roi = get_temperature_roi(model, img)
    if roi is None:
        print("[WARN] temperature bbox 없음")
        return

    disp = crop_display_area(roi)
    mask = extract_red_segments(disp)

    cv2.imwrite("debug_roi.png", roi)
    cv2.imwrite("debug_display_crop.png", disp)
    cv2.imwrite("debug_display_mask.png", mask)

    print("Saved: debug_roi.png, debug_display_crop.png, debug_display_mask.png")


# ----------------------------
# 실행
# ----------------------------
if __name__ == "__main__":
    model = YOLO("../../control-panel-5/runs/train/panel_yolo11n2/weights/best.pt")
    img_path = "origin/controller2.png"
    process_image(img_path, model)