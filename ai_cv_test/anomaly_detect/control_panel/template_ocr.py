import cv2
import numpy as np
from ultralytics import YOLO
import os

MODULE_MODEL_PATH = "../../AHU-module-detection/runs/train/module_yolo11n/weights/best.pt"
PANEL_MODEL_PATH = "../../control-panel-5/runs/train/panel_yolo11n2/weights/best.pt"
IMAGE_PATH = "origin/control_panel.jpeg"


# ========================================
# 1. 7-SEGMENT SEGMENTATION + TEMPLATE OCR
# ========================================
SEG_TEMPLATES = {
    0: [1,1,1,0,1,1,1],
    1: [0,0,1,0,0,1,0],
    2: [1,0,1,1,1,0,1],
    3: [1,0,1,1,0,1,1],
    4: [0,1,1,1,0,1,0],
    5: [1,1,0,1,0,1,1],
    6: [1,1,0,1,1,1,1],
    7: [1,0,1,0,0,1,0],
    8: [1,1,1,1,1,1,1],
    9: [1,1,1,1,0,1,1],
}


def extract_digit_segments(binary_img):
    h, w = binary_img.shape
    seg = []

    # 7개 segment 상대 위치 (대략적 비율로 처리 → 이미지 크기 상관 없음)
    segments = [
        (0.05, 0.05, 0.90, 0.15),  # top
        (0.05, 0.05, 0.15, 0.45),  # top-left
        (0.80, 0.05, 0.95, 0.45),  # top-right
        (0.05, 0.40, 0.90, 0.60),  # middle
        (0.05, 0.55, 0.15, 0.95),  # bottom-left
        (0.80, 0.55, 0.95, 0.95),  # bottom-right
        (0.05, 0.85, 0.90, 0.95),  # bottom
    ]

    for (x1r, y1r, x2r, y2r) in segments:
        x1, x2 = int(w * x1r), int(w * x2r)
        y1, y2 = int(h * y1r), int(h * y2r)
        area = binary_img[y1:y2, x1:x2]
        white_ratio = (area == 255).mean()
        seg.append(1 if white_ratio > 0.25 else 0)  # high threshold to avoid noise

    return seg


def match_digit(seg_pattern):
    best_digit = None
    best_score = 999

    for digit, tpl in SEG_TEMPLATES.items():
        diff = sum([abs(seg_pattern[i] - tpl[i]) for i in range(7)])
        if diff < best_score:
            best_score = diff
            best_digit = digit

    return best_digit


def template_ocr(mask_img):
    """ mask_img = threshold된 흰색 숫자(255), 배경(0) """

    # 숫자 컨투어 분리
    cnts, _ = cv2.findContours(mask_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=lambda c: cv2.boundingRect(c)[0])  # 왼→오 정렬

    digits = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w < 8 or h < 20:
            continue  # 너무 작은 경우 소수점(dot) 가능성
        digit_roi = mask_img[y:y+h, x:x+w]
        seg = extract_digit_segments(digit_roi)
        d = match_digit(seg)
        digits.append((x, d))

    # 소수점(dot) 탐지
    dot_pos = None
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w < 6 and h < 6:  # 작은 점
            dot_pos = x

    # 숫자 조합
    digits_sorted = [d for _, d in sorted(digits, key=lambda x: x[0])]
    if not digits_sorted:
        return None

    if dot_pos is None: 
        # 예: 159 → 15.9 보정
        if len(digits_sorted) >= 3:
            val = float(str(digits_sorted[0]) + str(digits_sorted[1]) + "." + str(digits_sorted[2]))
        elif len(digits_sorted) == 2:
            val = float(str(digits_sorted[0]) + "." + str(digits_sorted[1]))
        else:
            return float(digits_sorted[0])
    else:
        # dot이 위치한 곳 기준으로 분리
        nums = sorted(digits, key=lambda x: x[0])
        left = ""
        right = ""
        for x, d in nums:
            if x < dot_pos:
                left += str(d)
            else:
                right += str(d)
        val = float(left + "." + right)

    return val




# ========================================
# 2. LED 점등 여부 판단
# ========================================
def led_color_status(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    red = cv2.inRange(hsv, (0, 150, 150), (10, 255, 255)) | \
          cv2.inRange(hsv, (170, 150, 150), (180, 255, 255))
    green = cv2.inRange(hsv, (45, 120, 120), (85, 255, 255))
    yellow = cv2.inRange(hsv, (15, 150, 150), (35, 255, 255))

    masks = {"red": red, "green": green, "yellow": yellow}
    ratios = {k: (m > 0).mean() for k, m in masks.items()}
    dominant = max(ratios, key=ratios.get)

    is_on = ratios[dominant] > 0.10
    return is_on, ratios


# ========================================
# 3. 메인 프로그램
# ========================================
def main():
    module_model = YOLO(MODULE_MODEL_PATH)
    panel_model = YOLO(PANEL_MODEL_PATH)

    img = cv2.imread(IMAGE_PATH)
    if img is None:
        print("이미지 로드 실패:", IMAGE_PATH)
        return

    # 전체 → 패널 탐지
    mod_res = module_model.predict(img, conf=0.2, device="cpu", verbose=False)
    panel_roi = None
    for b in mod_res[0].boxes:
        cls = module_model.names[int(b.cls)]
        if "panel" in cls.lower():
            x1, y1, x2, y2 = map(int, b.xyxy[0])
            panel_roi = img[y1:y2, x1:x2]
            break

    if panel_roi is None:
        print("제어판 탐지 실패")
        return

    # 패널 내부 탐지
    btn_res = panel_model.predict(panel_roi, conf=0.4, device="cpu", verbose=False)
    led_status = {}
    temperature = None

    for b in btn_res[0].boxes:
        cls = panel_model.names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        roi = panel_roi[y1:y2, x1:x2]

        if cls == "temperature":
            # threshold
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)

            cv2.imwrite("ocr_mask_debug.jpg", mask)

            temperature = template_ocr(mask)

        else:
            on, ratios = led_color_status(roi)
            led_status[cls] = {"on": on, "ratios": ratios}

    print("결과 Temperature:", temperature)
    print("LED Status:", led_status)

    # 결과 저장
    base, ext = os.path.splitext(IMAGE_PATH)
    save_path = base + "_result.jpg"

    annotated = panel_roi.copy()
    cv2.imwrite(save_path, annotated)
    print("\n저장 완료:", save_path)


if __name__ == "__main__":
    main()
