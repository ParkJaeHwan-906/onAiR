import cv2
import numpy as np
import pytesseract
from ultralytics import YOLO


MODULE_MODEL_PATH = "-AHU-module-detection-2/runs/train/module_yolo11n/weights/best.pt"
PANEL_MODEL_PATH = "control-panel-2/runs/train/panel_yolo11n/weights/best.pt"
IMAGE_PATH = "KakaoTalk_Photo_2025-11-05-22-06-51.jpeg"
BRIGHTNESS_THRESH = 120



# 온도 탐지 함수 (OCR)
def ocr_temperature(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789."
    text = pytesseract.image_to_string(thresh, config=config)
    text = text.strip().replace("°", "")
    try:
        return float(text)
    except:
        return None

# LED 점등 여부 판단 
def led_color_status(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # 색상 범위 (두 구간으로 나눈 red 포함)
    red_mask1 = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
    red_mask2 = cv2.inRange(hsv, (170, 100, 100), (180, 255, 255))
    red_mask = cv2.bitwise_or(red_mask1, red_mask2)

    green_mask = cv2.inRange(hsv, (40, 40, 80), (90, 255, 255))
    yellow_mask = cv2.inRange(hsv, (15, 100, 100), (40, 255, 255))

    masks = {
        "red": red_mask,
        "green": green_mask,
        "yellow": yellow_mask,
    }

    color_ratios = {k: (mask > 0).mean() for k, mask in masks.items()}
    dominant_color = max(color_ratios, key=color_ratios.get)

    # --- 점등 여부 판단 (색 비율 기준) ---
    # 빨간불은 낮은 밝기여도 켜진 것으로 판단
    is_on = color_ratios[dominant_color] > 0.05

    return is_on, color_ratios




# 이상 판단 함수

def detect_abnormal(temp, led_status):
    if led_status.get("overheat", {}).get("on", False):
        return "⚠️ 과열 경고"
    if not led_status.get("power", {}).get("on", True):
        return "⚠️ 전원 꺼짐"
    if temp is not None and temp > 60:
        return f"⚠️ 온도 이상 ({temp:.1f}°C)"
    return "정상 상태"



# 시각화 함수
def draw_detection_results(img, results, led_status, temp_value, abnormal_msg):
    annotated = img.copy()

    # 버튼 박스 및 텍스트 표시
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

    # 최종 이상 판정 결과
    cv2.putText(annotated, abnormal_msg, (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                (0, 0, 255) if "⚠️" in abnormal_msg else (0, 255, 0), 3, cv2.LINE_AA)

    return annotated


# 6. 메인 로직

def main():
    module_model = YOLO(MODULE_MODEL_PATH)
    panel_model = YOLO(PANEL_MODEL_PATH)

    img = cv2.imread(IMAGE_PATH)
    if img is None:
        print("이미지 로드 실패:", IMAGE_PATH)
        return

    # ------------------------------
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

    # 2. 제어판 내부 구성 탐지
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

    # 3. 이상 탐지 판단
    result_msg = detect_abnormal(temp_value, led_status)

    print(f"온도: {temp_value if temp_value is not None else '인식 실패'}°C")
    for k, v in led_status.items():
        print(f"{k}: {'ON' if v['on'] else 'OFF'}  (색상 비율: {v['color']})")
    print("결론:", result_msg)

    # 4.시각화 및 저장

    annotated = draw_detection_results(panel_roi, button_results, led_status, temp_value, result_msg)
    cv2.imwrite("detected_panel_result.jpg", annotated)
    
    print("결과 이미지 저장 완료: detected_panel_result.jpg")

if __name__ == "__main__":
    main()
