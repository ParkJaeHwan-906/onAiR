import cv2
import numpy as np
import pytesseract
from ultralytics import YOLO
import re


MODULE_MODEL_PATH = "../../AHU-module-detection/runs/train/module_yolo11n/weights/best.pt"
PANEL_MODEL_PATH = "../../control-panel-part-detection/runs/train/panel_yolo11n2/weights/best.pt"
IMAGE_PATH = "KakaoTalk_Photo_2025-11-05-22-58-17 017.jpeg"


# ----------------------------
# 1. 온도 탐지 함수 (OCR 개선)
# ----------------------------
def ocr_temperature(img):
    h, w = img.shape[:2]
    crop = img[int(h * 0.2):int(h * 0.9), int(w * 0.25):int(w * 0.75)]

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    # 빨간색 LED 마스크 (두 구간)
    lower_red1 = np.array([0, 120, 80])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 120, 80])
    upper_red2 = np.array([180, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    # morphology 보정 (소수점 유지 + 숫자 연결 강화)
    kernel = np.ones((2, 2), np.uint8)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # 🔍 디버그용 저장
    cv2.imwrite("temp_roi_debug.jpg", crop)
    cv2.imwrite("temp_redmask_debug.jpg", red_mask)

    # OCR
    config = "--psm 7 -c tessedit_char_whitelist=0123456789."
    text = pytesseract.image_to_string(red_mask, config=config).strip()

    import re
    match = re.search(r"\d+(\.\d+)?", text)
    if match:
        value = float(match.group())
        if value > 100:
            value = value / 10
        return value

    return None







# ----------------------------
# 2. LED 점등 여부 판단
# ----------------------------
def led_color_status(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # 색상 범위 (red는 두 구간)
    red_mask1 = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
    red_mask2 = cv2.inRange(hsv, (170, 100, 100), (180, 255, 255))
    red_mask = cv2.bitwise_or(red_mask1, red_mask2)
    green_mask = cv2.inRange(hsv, (40, 40, 80), (90, 255, 255))
    yellow_mask = cv2.inRange(hsv, (15, 100, 100), (40, 255, 255))

    masks = {"red": red_mask, "green": green_mask, "yellow": yellow_mask}
    color_ratios = {k: (mask > 0).mean() for k, mask in masks.items()}
    dominant_color = max(color_ratios, key=color_ratios.get)

    # 점등 판단
    is_on = color_ratios[dominant_color] > 0.05
    return is_on, color_ratios


# ----------------------------
# 3. 이상 판단 함수
# ----------------------------
def detect_abnormal(temp, led_status):
    if led_status.get("overheat", {}).get("on", False):
        return "⚠️ 과열 경고"
    if not led_status.get("power", {}).get("on", True):
        return "⚠️ 전원 꺼짐"
    if temp is not None and temp > 60:
        return f"⚠️ 온도 이상 ({temp:.1f}°C)"
    return "정상 상태"


# ----------------------------
# 4. 시각화 함수 (OCR 실패 표시 포함)
# ----------------------------
def draw_detection_results(img, results, led_status, temp_value, abnormal_msg):
    annotated = img.copy()

    for b in results[0].boxes:
        cls = results[0].names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        color = (0, 255, 0)
        label = cls

        if cls == "temperature":
            if temp_value is None:
                label += ": OCR 실패"
                color = (0, 0, 255)
            else:
                label += f": {temp_value:.1f}°C"
                color = (255, 255, 0)
        else:
            if led_status.get(cls, {}).get("on", False):
                label += " (ON)"
                color = (0, 255, 0)
            else:
                label += " (OFF)"
                color = (0, 0, 255)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(annotated, label, (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)

    cv2.putText(annotated, abnormal_msg, (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                (0, 0, 255) if "⚠️" in abnormal_msg else (0, 255, 0), 3, cv2.LINE_AA)

    return annotated


# ----------------------------
# 5. 메인 로직
# ----------------------------
def main():
    module_model = YOLO(MODULE_MODEL_PATH)
    panel_model = YOLO(PANEL_MODEL_PATH)

    img = cv2.imread(IMAGE_PATH)
    if img is None:
        print("이미지 로드 실패:", IMAGE_PATH)
        return

    # ① AHU 전체 → 제어판 탐지
    module_results = module_model.predict(img, conf=0.2, device="cpu", verbose=False)
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
    button_results = panel_model.predict(panel_roi, conf=0.2, device="cpu", verbose=False)
    led_status, temp_value = {}, None

    for b in button_results[0].boxes:
        cls = panel_model.names[int(b.cls)]
        print("탐지된 클래스:", cls)
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        roi = panel_roi[y1:y2, x1:x2]

        if cls == "temperature":
            temp_value = ocr_temperature(roi)
        else:
            is_on, color_info = led_color_status(roi)
            led_status[cls] = {"on": is_on, "color": color_info}

    # ③ 이상 탐지
    result_msg = detect_abnormal(temp_value, led_status)

    print(f"온도: {temp_value if temp_value is not None else '인식 실패'}°C")
    for k, v in led_status.items():
        print(f"{k}: {'ON' if v['on'] else 'OFF'}  (색상 비율: {v['color']})")
    print("결론:", result_msg)

    # ④ 시각화 및 저장
    annotated = draw_detection_results(panel_roi, button_results, led_status, temp_value, result_msg)
    cv2.imwrite("detected_panel_result4.jpg", annotated)
    print("결과 이미지 저장 완료: detected_panel_result4.jpg")


if __name__ == "__main__":
    main()
