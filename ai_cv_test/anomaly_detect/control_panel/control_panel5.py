import cv2
import numpy as np
from ultralytics import YOLO
import pytesseract

# =========================================
# 1) 빨간 LED 세그먼트 마스크 생성
# =========================================
def extract_red_segments(roi):
    # Blur로 노이즈 완화
    blur = cv2.GaussianBlur(roi, (5, 5), 0)

    # HSV 변환
    hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)

    # 강한 빨간색 LED 기준 HSV 범위
    lower_red1 = np.array([0, 150, 150])
    upper_red1 = np.array([10, 255, 255])

    lower_red2 = np.array([170, 150, 150])
    upper_red2 = np.array([180, 255, 255])

    # 두 영역을 OR
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = mask1 | mask2

    # Morphology로 노이즈 감소
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.medianBlur(mask, 5)

    # OCR 잘 되도록 2~3배 업스케일
    mask_big = cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR)

    return mask_big


# =========================================
# 2) YOLO로 temperature display ROI 검출
# =========================================
def get_temperature_roi(model, img):
    results = model(img)[0]

    best_box = None
    best_conf = 0

    for box in results.boxes:
        cls = int(box.cls)
        conf = float(box.conf)

        # 'temperature' 클래스만 사용
        if model.names[cls] == "temperature":
            if conf > best_conf:
                best_conf = conf
                best_box = box

    if best_box is None:
        return None

    x1, y1, x2, y2 = map(int, best_box.xyxy[0])
    roi = img[y1:y2, x1:x2]

    return roi


# =========================================
# 3) ROI 내부에서 실제 숫자 디스플레이만 Crop
#    (기기 형상 기준 비율 조정)
# =========================================
def crop_display_area(roi):
    h, w, _ = roi.shape

    # 실제 촬영 이미지 기반으로 최적화한 비율
    top = int(h * 0.20)
    bottom = int(h * 0.80)
    left = int(w * 0.20)
    right = int(w * 0.85)

    disp = roi[top:bottom, left:right]
    return disp


# =========================================
# 4) Tesseract OCR (옵션)
# =========================================
def ocr_tesseract(mask):
    config = "--psm 7 -c tessedit_char_whitelist=0123456789."
    text = pytesseract.image_to_string(mask, config=config)
    return text.strip()


# =========================================
# 5) 전체 파이프라인 실행
# =========================================
def process_image(img_path, model, use_ocr=True):
    img = cv2.imread(img_path)

    # 1) YOLO temperature bbox 찾기
    roi = get_temperature_roi(model, img)
    if roi is None:
        print("[WARN] temperature bbox 없음")
        return

    # 2) ROI에서 디스플레이만 crop
    disp = crop_display_area(roi)

    # 3) 빨간 LED 마스크 생성
    mask = extract_red_segments(disp)

    # ----------------------------------
    # 4) OCR (옵션)
    # ----------------------------------
    ocr_result = None
    if use_ocr:
        ocr_result = ocr_tesseract(mask)
        print("Tesseract OCR:", ocr_result)

    # 5) 디버그 이미지 저장
    cv2.imwrite("debug_roi.png", roi)
    cv2.imwrite("debug_display_crop.png", disp)
    cv2.imwrite("debug_display_mask.png", mask)

    print("Saved: debug_roi.png, debug_display_crop.png, debug_display_mask.png")

    return ocr_result


# =========================================
# 실행
# =========================================
if __name__ == "__main__":
    model = YOLO("../../control-panel-5/runs/train/panel_yolo11n2/weights/best.pt")
    img_path = "origin/controller2.png"  # 테스트 이미지

    result = process_image(img_path, model, use_ocr=True)
