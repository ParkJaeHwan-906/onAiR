"""
제어판 이상 탐지 (LED + 온도 OCR)
- run_anomaly_detection()에서 선택한 sharpest_frame과 module_boxes를 전달받음
- module_boxes에서 panel 박스를 찾아 ROI 추출
- panel_best.pt로 LED / 온도 분석
"""
import cv2
import pytesseract
import numpy as np
from loguru import logger
from ultralytics import YOLO

PANEL_MODEL_PATH = "/app/ai_server/yolo_service/models/panel_best.pt"

_panel_model = None


def _load_panel_model_once():
    global _panel_model
    if _panel_model is None:
        _panel_model = YOLO(str(PANEL_MODEL_PATH))
        logger.info("panel_anomaly: Panel YOLO loaded")


# RAG-friendly 메시지 매핑
PANEL_RAG_MESSAGE = {
    "normal": "제어판은 정상 상태입니다",
    "overheat": "제어판에서 과열 경고가 감지되었습니다",
    "power_off": "제어판 전원이 꺼져 있거나 전원 LED가 꺼져 있습니다",
    "temp_high": "제어판 온도가 비정상적으로 높습니다",
    "no_frame": "입력 프레임이 없어 제어판 상태를 분석하지 못했습니다",
    "no_modules": "모듈 탐지 결과가 없어 제어판을 찾지 못했습니다",
    "panel_not_found": "제어판 모듈 박스를 찾지 못했습니다",
    "empty_roi": "제어판 ROI가 비어 있어 분석할 수 없습니다",
    "exception": "제어판 분석 중 예외가 발생했습니다"
}


# LED 색상 판별
def led_color_status(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    red = cv2.inRange(hsv, (0, 150, 120), (10, 255, 255)) | \
          cv2.inRange(hsv, (170, 150, 120), (180, 255, 255))

    green = cv2.inRange(hsv, (45, 120, 120), (85, 255, 255))

    yellow = cv2.inRange(hsv, (18, 170, 170), (32, 255, 255))

    masks = {"red": red, "green": green, "yellow": yellow}
    ratios = {k: (m > 0).mean() for k, m in masks.items()}

    dominant = max(ratios, key=ratios.get)
    is_on = ratios[dominant] > 0.18

    return is_on, dominant, ratios


# 빨간 LED 세그먼트 마스크 추출
def extract_red_segments(roi):
    b, g, r = cv2.split(roi)
    red_strong = (r > 150) & (r > g + 30) & (r > b + 30)
    mask = red_strong.astype(np.uint8) * 255

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=1)

    mask_big = cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR)
    return mask_big


# temperature ROI 추출 (현재는 사용하지 않지만 남겨둠)
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
    return img[y1:y2, x1:x2]


# 디스플레이 영역 crop
def crop_display_area(roi):
    h, w, _ = roi.shape
    top = int(h * 0.25)
    bottom = int(h * 0.77)
    left = int(w * 0.22)
    right = int(w * 0.77)
    return roi[top:bottom, left:right]


# OCR
def ocr_temperature(roi):
    if roi is None or roi.size == 0:
        return None
    roi = cv2.resize(roi, None, fx=3.0, fy=3.0)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789."
    txt = pytesseract.image_to_string(th, config=config).strip()
    try:
        return float(txt)
    except Exception:
        return None


# 이상 판단
def detect_abnormal(temp, led_status):
    if led_status.get("overheat", {}).get("on", False):
        return "overheat"
    if not led_status.get("power", {}).get("on", True):
        return "power_off"
    if temp is not None and temp > 60:
        return "temp_high"
    return "normal"


# 메인: panel 분석
async def analyze_panel(sharpest_frame, best_score, module_boxes):
    try:
        if sharpest_frame is None:
            detail = "no_frame"
            return {
                "type": "panel",
                "status": "unknown",
                "detail": detail,
                "message": PANEL_RAG_MESSAGE.get(detail, "입력 프레임 없음"),
                "sharpness": None,
                "results": {}
            }

        if not module_boxes:
            detail = "no_modules"
            return {
                "type": "panel",
                "status": "not_found",
                "detail": detail,
                "message": PANEL_RAG_MESSAGE.get(detail, "모듈 탐지 결과 없음"),
                "sharpness": best_score,
                "results": {}
            }

        panel_boxes = [b for b in module_boxes if "panel" in b["label"].lower()]
        if not panel_boxes:
            detail = "panel_not_found"
            return {
                "type": "panel",
                "status": "not_found",
                "detail": detail,
                "message": PANEL_RAG_MESSAGE.get(detail, "제어판 모듈 미검출"),
                "sharpness": best_score,
                "results": {}
            }

        panel_box = max(panel_boxes, key=lambda b: b.get("confidence", 0.0))
        x1, y1, x2, y2 = map(int, panel_box["xyxy"])
        panel_roi = sharpest_frame[y1:y2, x1:x2]

        if panel_roi is None or panel_roi.size == 0:
            detail = "empty_roi"
            return {
                "type": "panel",
                "status": "not_found",
                "detail": detail,
                "message": PANEL_RAG_MESSAGE.get(detail, "제어판 ROI가 비어 있음"),
                "sharpness": best_score,
                "results": {}
            }

        _load_panel_model_once()

        panel_results = _panel_model.predict(panel_roi, conf=0.5, verbose=False)

        led_status = {}
        temperature_val = None

        for r in panel_results:
            for box in r.boxes:
                cls = _panel_model.names[int(box.cls)]
                conf = float(box.conf)
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                roi = panel_roi[y1:y2, x1:x2]
                if roi.size == 0:
                    continue

                name = cls.lower()

                if "led" in name or "button" in name:
                    is_on, color, ratios = led_color_status(roi)
                    led_status[cls] = {
                        "on": is_on,
                        "color": color,
                        "ratios": ratios,
                        "confidence": conf,
                    }

                elif "temp" in name or "temperature" in name:
                    t_roi = crop_display_area(roi)
                    mask = extract_red_segments(t_roi)
                    temperature_val = ocr_temperature(mask)

        anomaly = detect_abnormal(temperature_val, led_status)
        detail = anomaly  # normal, overheat, power_off, temp_high
        status = "anomaly" if anomaly != "normal" else "normal"
        message = PANEL_RAG_MESSAGE.get(
            detail,
            "제어판 상태를 판단할 수 없습니다"
        )

        return {
            "type": "panel",
            "status": status,
            "detail": detail,
            "message": message,
            "sharpness": best_score,
            "results": {
                "temperature": temperature_val,
                "leds": led_status,
            }
        }

    except Exception as e:
        logger.exception(f"[panel] error: {e}")
        detail = "exception"
        return {
            "type": "panel",
            "status": "error",
            "detail": detail,
            "message": PANEL_RAG_MESSAGE.get(detail, str(e)),
            "sharpness": best_score,
            "results": {}
        }
