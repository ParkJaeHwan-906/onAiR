import os
import cv2
import pytesseract
import numpy as np
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_MODEL_PATH = os.path.join(BASE_DIR, "../../../models/module_best.pt")
PANEL_MODEL_PATH = os.path.join(BASE_DIR, "../../../models/panel_best.pt")


def led_color_status(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    red_mask = cv2.bitwise_or(
        cv2.inRange(hsv, (0, 100, 100), (10, 255, 255)),
        cv2.inRange(hsv, (170, 100, 100), (180, 255, 255))
    )
    green_mask = cv2.inRange(hsv, (40, 40, 80), (90, 255, 255))
    yellow_mask = cv2.inRange(hsv, (15, 100, 100), (40, 255, 255))
    masks = {"red": red_mask, "green": green_mask, "yellow": yellow_mask}
    ratios = {k: (mask > 0).mean() for k, mask in masks.items()}
    dominant = max(ratios, key=ratios.get)
    return ratios[dominant] > 0.05, dominant


def ocr_temperature(roi):
    roi = cv2.resize(roi, None, fx=3.0, fy=3.0)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789."
    text = pytesseract.image_to_string(thresh, config=config).strip()
    try:
        return float(text)
    except:
        return None


# -------------------------------
# 다프레임 voting 제어판 이상 탐지
# -------------------------------
async def analyze_panel(frames):
    """제어판 이상 탐지 (LED flicker 완화용 voting)"""
    if not frames:
        return {"type": "panel", "status": "unknown", "message": "프레임 없음"}

    module_model, panel_model = YOLO(MODULE_MODEL_PATH), YOLO(PANEL_MODEL_PATH)
    frame_samples = frames[-3:] if len(frames) > 3 else frames
    panel_results = []
    temp_values = []

    for frame in frame_samples:
        module_results = module_model.predict(frame, conf=0.5, device="cpu", verbose=False)
        panel_roi = None
        for box in module_results[0].boxes:
            cls = module_model.names[int(box.cls)]
            if "panel" in cls.lower():
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                panel_roi = frame[y1:y2, x1:x2]
                break

        if panel_roi is None:
            continue

        button_results = panel_model.predict(panel_roi, conf=0.5, device="cpu", verbose=False)
        led_status = {}
        for box in button_results[0].boxes:
            cls = panel_model.names[int(box.cls)]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            roi = panel_roi[y1:y2, x1:x2]
            if cls == "temperature":
                temp = ocr_temperature(roi)
                if temp is not None:
                    temp_values.append(temp)
            else:
                on, color = led_color_status(roi)
                led_status[cls] = {"on": on, "color": color}

        panel_results.append(led_status)

    # --- flicker voting ---
    if not panel_results:
        return {"type": "panel", "status": "not_found", "message": "제어판 탐지 실패"}

    merged_status = {}
    for key in {k for d in panel_results for k in d.keys()}:
        states = [d[key]["on"] for d in panel_results if key in d]
        colors = [d[key]["color"] for d in panel_results if key in d]
        if not states:
            continue
        on_ratio = sum(states) / len(states)
        dominant_color = max(set(colors), key=colors.count)
        merged_status[key] = {"on": on_ratio > 0.5, "color": dominant_color}

    # --- 온도 voting ---
    if temp_values:
        temp_mean = np.mean(temp_values)
    else:
        temp_mean = None

    # --- 판정 ---
    if not merged_status:
        return {"type": "panel", "status": "low_confidence", "message": "LED 인식 실패"}

    msg = "정상"
    if any(v["color"] == "red" for v in merged_status.values()):
        msg = "⚠️ 경고등 점등"
    elif temp_mean and temp_mean > 60:
        msg = f"⚠️ 온도 이상 ({temp_mean:.1f}°C)"

    return {
        "type": "panel",
        "status": "done",
        "message": msg,
        "temp": temp_mean,
        "leds": merged_status
    }
