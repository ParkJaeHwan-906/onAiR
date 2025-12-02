import cv2
import numpy as np
import pytesseract
from ultralytics import YOLO


MODULE_MODEL_PATH = "../../AHU-module-detection/runs/train/module_yolo11n/weights/best.pt"
PANEL_MODEL_PATH = "../../control-panel-part-detection/runs/train/panel_yolo11n2/weights/best.pt"
IMAGE_PATH = "control_panel2.jpeg"
BRIGHTNESS_THRESH = 120


# -----------------------------------------------------
# 1️⃣ 온도 탐지 함수 (빨간 LED 색상 강조 OCR)
# -----------------------------------------------------
def ocr_temperature(img):
    h, w = img.shape[:2]
    crop = img[int(h * 0.2):int(h * 0.9), int(w * 0.25):int(w * 0.75)]

    # HSV 변환 후 빨간색 영역만 마스크
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    # 마스크 적용 → 빨간 부분만 남김
    red_only = cv2.bitwise_and(crop, crop, mask=red_mask)

    # 흑백 변환 및 대비 강화
    gray = cv2.cvtColor(red_only, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # 이진화 (숫자 밝기 강조)
    _, thresh = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY)

    # 🔍 디버그용 이미지 저장
    cv2.imwrite("temp_roi_debug.jpg", crop)
    cv2.imwrite("temp_mask_debug.jpg", red_mask)
    cv2.imwrite("temp_thresh_debug.jpg", thresh)

    # OCR 실행
    config = "--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789."
    text = pytesseract.image_to_string(thresh, config=config)
    text = text.strip().replace("°", "")

    # 숫자만 추출
    import re
    match = re.search(r"\d+(\.\d+)?", text)
    if match:
        value = float(match.group())
        # 100 이상 값은 잘못 인식된 경우 보정
        if value > 100:
            value /= 10
        return value

    return None


# -----------------------------------------------------
# 2️⃣ LED 점등 여부 판단
# -----------------------------------------------------
def led_color_status(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    red_mask1 = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
    red_mask2 = cv2.inRange(hsv, (170, 100, 100), (180, 255, 255))
    red_mask = cv2.bitwise_or(red_mask1, red_mask2)
    green_mask = cv2.inRange(hsv, (40, 40, 80), (90, 255, 255))
    yellow_mask = cv2.inRange(hsv, (15, 100, 100), (40, 255, 255))

    masks = {"red": red_mask, "green": green_mask, "yellow": yellow_mask}
    color_ratios = {k: (mask > 0).mean() for k, mask in masks.items()}
    dominant_color = max(color_ratios, key=color_ratios.get)
    is_on = color_ratios[dominant_color] > 0.05
    return is_on, color_ratios


# -----------------------------------------------------
# 3️⃣ 이상 판단 함수
# -----------------------------------------------------
def detect_abnormal(temp, led_status):
    if led_status.get("overheat", {}).get("on", False):
        return "⚠️ 과열 경고"
    if not led_status.get("power", {}).get("on", True):
        return "⚠️ 전원 꺼짐"
    if temp is not None and temp > 60:
        return f"⚠️ 온도 이상 ({temp:.1f}°C)"
    return "정상 상태"


# -----------------------------------------------------
# 4️⃣ 시각화 함수
# -----------------------------------------------------
def draw_detection_results(img, results, led_status, temp_value, abnormal_msg):
    annotated = img.copy()

    for b in results[0].boxes:
        cls = results[0].names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])

        color = (0, 255, 0)
        label = cls

        if cls == "temperature":
            label += f": {temp_value if temp_value is not None else 'N/A'}°C"
        else:
            if led_status.get(cls, {}).get("on", False):
                color = (0, 255, 0)
                label += " (ON)"
            else:
                color = (0, 0, 255)
                label += " (OFF)"

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(annotated, label, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)

    cv2.putText(annotated, abnormal_msg, (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                (0, 0, 255) if "⚠️" in abnormal_msg else (0, 255, 0), 3, cv2.LINE_AA)

    return annotated


# -----------------------------------------------------
# 5️⃣ 메인 로직
# -----------------------------------------------------
def main():
    module_model = YOLO(MODULE_MODEL_PATH)
    panel_model = YOLO(PANEL_MODEL_PATH)

    img = cv2.imread(IMAGE_PATH)
    if img is None:
        print("이미지 로드 실패:", IMAGE_PATH)
        return

    # ① AHU 전체 → 제어판 탐지
    module_results = module_model.predict(img, conf=0.5, device="cpu", verbose=False)
    panel_roi = None
    for box in module_results[0].boxes:
        cls_name = module_model.names[int(box.cls)]
        if "panel" in cls_name.lower():
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            panel_roi = img[y1:y2, x1:x2]
            break
    if panel_roi is None:
        print("제어판 탐지 실패")
        return

    # ② 제어판 내부 구성 탐지
    button_results = panel_model.predict(panel_roi, conf=0.5, device="cpu", verbose=False)
    led_status = {}
    temp_value = None

    for b in button_results[0].boxes:
        cls = panel_model.names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        roi = panel_roi[y1:y2, x1:x2]

        if cls == "temperature":
            temp_value = ocr_temperature(roi)
        else:
            is_on, color_info = led_color_status(roi)
            led_status[cls] = {"on": is_on, "color": color_info}

    # ③ 이상 판단
    result_msg = detect_abnormal(temp_value, led_status)

    print(f"온도: {temp_value if temp_value is not None else '인식 실패'}°C")
    for k, v in led_status.items():
        print(f"{k}: {'ON' if v['on'] else 'OFF'}  (색상 비율: {v['color']})")
    print("결론:", result_msg)

    # ④ 시각화 및 저장
    annotated = draw_detection_results(panel_roi, button_results, led_status, temp_value, result_msg)
    cv2.imwrite("detected_panel_result3.jpg", annotated)
    print("결과 이미지 저장 완료: detected_panel_result3.jpg")


if __name__ == "__main__":
    main()
