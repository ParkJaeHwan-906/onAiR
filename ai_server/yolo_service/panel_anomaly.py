"""
제어판 이상 탐지 (LED + 온도 OCR)
- sharpness 기반으로 가장 선명한 프레임 1장 선택
- Module YOLO → panel ROI 추출
- Panel YOLO → LED / 온도 분석
"""

import os
import cv2
import pytesseract
import numpy as np
from pathlib import Path
from loguru import logger
from ultralytics import YOLO


# ------------------------------
# 모델 경로
# ------------------------------
BASE_DIR = Path(__file__).resolve().parent
MODULE_MODEL_PATH = BASE_DIR / "../models/module_best.pt"
PANEL_MODEL_PATH = BASE_DIR / "../models/panel_best.pt"

# ------------------------------
# 하이퍼파라미터
# ------------------------------
MIN_SHARPNESS = 70.0     # 흐린 프레임 필터링 기준

_module_model = None      # lazy-loaded
_panel_model = None


# ------------------------------
# 유틸 함수 (sharpness, LED 색상, OCR)
# ------------------------------
def calc_sharpness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


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
    except Exception:
        return None


# ------------------------------
# lazy YOLO loader
# ------------------------------
def _load_models_once():
    global _module_model, _panel_model

    if _module_model is None:
        _module_model = YOLO(str(MODULE_MODEL_PATH))
        _module_model.fuse()
        logger.info("📦 panel_anomaly: Module YOLO 로드 완료")

    if _panel_model is None:
        _panel_model = YOLO(str(PANEL_MODEL_PATH))
        logger.info("📦 panel_anomaly: Panel YOLO 로드 완료")


# ------------------------------
# 제어판 이상 탐지 메인 함수
# ------------------------------
async def analyze_panel(frames, module_info=None):
    """
    panel_anomaly는 run_anomaly_detection()에서 module_info로
    이미 panel box를 전달받을 수도 있음.
    
    frames: 프레임 리스트
    module_info: {"label": "panel", "confidence": ..., "box": [...] }
    """

    try:
        if not frames:
            return {"type": "panel", "status": "unknown", "message": "입력 프레임 없음"}

        # ------------------------------
        # 1. sharpest frame 선택
        # ------------------------------
        sharp_list = [(f, calc_sharpness(f)) for f in frames]
        sharp_list = [(f, s) for f, s in sharp_list if s > MIN_SHARPNESS]

        if not sharp_list:
            return {"type": "panel", "status": "low_confidence", "message": "모든 프레임이 흐림"}

        sharpest_frame, best_score = max(sharp_list, key=lambda x: x[1])

        # ------------------------------
        # 2. 모델 로드
        # ------------------------------
        _load_models_once()

        # ------------------------------
        # 3. panel ROI 추출
        # ------------------------------
        if module_info and "box" in module_info:
            # run_anomaly_detection()에서 전달된 panel box 우선 사용
            x1, y1, x2, y2 = map(int, module_info["box"])
            panel_roi = sharpest_frame[y1:y2, x1:x2]
        else:
            # module YOLO로 box 탐지
            mod_results = _module_model.predict(sharpest_frame, conf=0.5, verbose=False)
            panel_roi = None
            for r in mod_results:
                for box in r.boxes:
                    cls = _module_model.names[int(box.cls)]
                    if "panel" in cls.lower():
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        panel_roi = sharpest_frame[y1:y2, x1:x2]
                        break

        if panel_roi is None or panel_roi.size == 0:
            return {
                "type": "panel",
                "status": "not_found",
                "sharpness": best_score,
                "message": "제어판 미검출"
            }

        # ------------------------------
        # 4. Panel YOLO로 LED/온도 분석
        # ------------------------------
        panel_results = _panel_model.predict(panel_roi, conf=0.5, verbose=False)

        leds = {}
        temp = None

        for r in panel_results:
            for box in r.boxes:
                cls = _panel_model.names[int(box.cls)]
                conf = float(box.conf)
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                roi = panel_roi[y1:y2, x1:x2]
                if roi.size == 0:
                    continue

                cls_lower = cls.lower()

                if "led" in cls_lower or "button" in cls_lower:
                    is_on, color = led_color_status(roi)
                    leds[cls] = {
                        "status": "on" if is_on else "off",
                        "color": color,
                        "confidence": conf
                    }

                elif "temp" in cls_lower or "temperature" in cls_lower:
                    t = ocr_temperature(roi)
                    if t is not None:
                        temp = t

        # ------------------------------
        # 5. 이상 판단
        # ------------------------------
        has_anomaly = False

        if temp is not None and (temp > 80 or temp < 5):
            has_anomaly = True

        for led_state in leds.values():
            if led_state["status"] == "on" and led_state["color"] == "red":
                has_anomaly = True
                break

        return {
            "type": "panel",
            "status": "anomaly" if has_anomaly else "normal",
            "sharpness": best_score,
            "message": "이상 탐지됨" if has_anomaly else "정상",
            "results": {
                "leds": leds,
                "temp": temp
            }
        }

    except Exception as e:
        logger.exception(f"[panel] 분석 오류: {e}")
        return {"type": "panel", "status": "error", "message": str(e)}
