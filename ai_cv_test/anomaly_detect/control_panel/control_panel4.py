import cv2
import numpy as np
import pytesseract
from ultralytics import YOLO
import re
import os

MODULE_MODEL_PATH = "../../On_AiR-1/runs/train/onAiR_yolo11n/weights/best.pt"
PANEL_MODEL_PATH = "../../On_AiR-1/runs/train/onAiR_yolo11n/weights/best.pt"
IMAGE_PATH = "./origin/KakaoTalk_20251113_020310326_05.jpg"


# ----------------------------
# 1. 온도 탐지 함수 (OCR 개선)
# ----------------------------
# def ocr_temperature(img):
#     import re

#     h, w = img.shape[:2]
#     crop = img[int(h*0.15):int(h*0.85), int(w*0.15):int(w*0.85)]

#     hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

#     # LED 세그먼트: red 기반으로 추출
#     mask = (
#         cv2.inRange(hsv, (0, 70, 70), (10, 255, 255)) |
#         cv2.inRange(hsv, (170, 70, 70), (180, 255, 255))
#     )

#     # 🔥 핵심1: 세그먼트 숫자 굵기 강화
#     kernel = np.ones((5,5), np.uint8)
#     mask = cv2.dilate(mask, kernel, iterations=2)
#     mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

#     # 🔥 핵심2: OCR 확대
#     mask_big = cv2.resize(mask, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)

#     cv2.imwrite("ocr_mask_debug_after.jpg", mask_big)

#     # 🔢 OCR 시도
#     for psm in [7, 13, 6]:
#         config = f"--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789."
#         txt = pytesseract.image_to_string(mask_big, config=config).strip()
#         m = re.search(r"\d+(\.\d+)?", txt)
#         if m:
#             v = float(m.group())
#             if v > 100: v /= 10
#             return v

    # return None



# ----------------------------
# 2. LED 점등 여부 판단 (색 범위 개선)
# ----------------------------
def led_color_status(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    red = cv2.inRange(hsv, (0, 150, 120), (10, 255, 255)) | \
          cv2.inRange(hsv, (170, 150, 120), (180, 255, 255))

    green = cv2.inRange(hsv, (45, 120, 120), (85, 255, 255))

    # 🔥 노랑 범위 강화: 반사광 제거
    yellow = cv2.inRange(hsv, (18, 170, 170), (32, 255, 255))

    masks = {"red": red, "green": green, "yellow": yellow}
    ratios = {k: (m > 0).mean() for k, m in masks.items()}

    dominant = max(ratios, key=ratios.get)

    # 🔥 켜짐 기준을 0.10 → 0.18로 조정해 반사광 억제
    is_on = ratios[dominant] > 0.18

    return is_on, ratios


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
# 4. 시각화 함수
# ----------------------------
def draw_detection_results(img, results, led_status, temp_value, abnormal_msg):
    annotated = img.copy()

    for b in results[0].boxes:
        cls = results[0].names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        color = (0, 255, 0)
        label = cls

        # if cls == "temperature":
        #     if temp_value is None:
        #         label += ": OCR 실패"
        #         color = (0, 0, 255)
        #     else:
        #         label += f": {temp_value:.1f}°C"
        #         color = (255, 255, 0)
        # else:
        if led_status.get(cls, {}).get("on", False):
            label += " (ON)"
            color = (0, 255, 0)
        else:
            label += " (OFF)"
            color = (0, 0, 255)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(annotated, label, (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    cv2.putText(annotated, abnormal_msg, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (0, 0, 255) if "⚠️" in abnormal_msg else (0, 255, 0), 3)
    return annotated


# ----------------------------
# 5. 메인
# ----------------------------
def main():
    module_model = YOLO(MODULE_MODEL_PATH)
    panel_model = YOLO(PANEL_MODEL_PATH)

    img = cv2.imread(IMAGE_PATH)
    if img is None:
        print("이미지 로드 실패:", IMAGE_PATH)
        return

    # 제어판 탐지
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

    # 내부 구성 탐지
    button_results = panel_model.predict(panel_roi, conf=0.5, device="cpu", verbose=False)
    led_status, temp_value = {}, None

    for b in button_results[0].boxes:
        cls = panel_model.names[int(b.cls)]
        print("탐지된 클래스:", cls)

        x1, y1, x2, y2 = map(int, b.xyxy[0])
        roi = panel_roi[y1:y2, x1:x2]

        # if cls == "temperature":
        #     temp_value = ocr_temperature(roi)
        # else:
        #     is_on, ratio = led_color_status(roi)
        #     led_status[cls] = {"on": is_on, "color": ratio}

    result_msg = detect_abnormal(temp_value, led_status)

    # ----------------------------
    # 🔥 최종 이미지 저장 이름 자동 생성
    # ----------------------------
    base, ext = os.path.splitext(IMAGE_PATH)
    save_name = f"{base}_result{ext}"

    annotated = draw_detection_results(panel_roi, button_results, led_status, temp_value, result_msg)
    cv2.imwrite(save_name, annotated)

    print(f"결과 저장 완료 → {save_name}")


if __name__ == "__main__":
    main()
