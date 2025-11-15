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

# panel 전용 YOLO 모델 경로
PANEL_MODEL_PATH = "/app/ai_server/yolo_service/models/panel_best.pt"

_panel_model = None  # lazy-loaded

# ------------------------------
# 유틸 함수 (LED 색상, OCR)
# ------------------------------
def led_color_status(roi):
    """LED ROI에서 주요 색상 추출"""
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    red_mask = cv2.bitwise_or(
        cv2.inRange(hsv, (0, 100, 100), (10, 255, 255)),
        cv2.inRange(hsv, (170, 100, 100), (180, 255, 255)),
    )
    green_mask = cv2.inRange(hsv, (40, 40, 80), (90, 255, 255))
    yellow_mask = cv2.inRange(hsv, (15, 100, 100), (40, 255, 255))

    masks = {"red": red_mask, "green": green_mask, "yellow": yellow_mask}
    ratios = {k: (mask > 0).mean() for k, mask in masks.items()}

    dominant = max(ratios, key=ratios.get)
    return ratios[dominant] > 0.05, dominant


def ocr_temperature(roi):
    """온도 숫자 OCR"""
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
# panel YOLO lazy loader
# ------------------------------
def _load_panel_model_once():
    global _panel_model
    if _panel_model is None:
        _panel_model = YOLO(str(PANEL_MODEL_PATH))
        logger.info("panel_anomaly: Panel YOLO 로드 완료")


# ------------------------------
# 제어판 이상 탐지 메인 함수
# ------------------------------
async def analyze_panel(sharpest_frame, best_score, module_boxes):
    """
    제어판 이상 탐지
    sharpest_frame: run_anomaly_detection()에서 선택한 가장 선명한 프레임 (np.ndarray)
    best_score: 해당 프레임의 sharpness 값 (float)
    module_boxes: module_best YOLO 결과 리스트
                  [{"label": str, "confidence": float, "xyxy": (x1, y1, x2, y2)}, ...]
    """
    try:
        if sharpest_frame is None:
            return {
                "type": "panel",
                "status": "unknown",
                "message": "입력 프레임 없음",
            }

        if not module_boxes:
            return {
                "type": "panel",
                "status": "not_found",
                "sharpness": best_score,
                "message": "모듈 탐지 결과 없음",
            }

        # 1. module_boxes에서 panel 박스 찾기
        panel_boxes = [
            b for b in module_boxes if "panel" in b["label"].lower()
        ]

        if not panel_boxes:
            return {
                "type": "panel",
                "status": "not_found",
                "sharpness": best_score,
                "message": "제어판 모듈 미검출",
            }

        # 가장 confidence 높은 panel 박스 사용
        panel_box = max(panel_boxes, key=lambda b: b.get("confidence", 0.0))
        x1, y1, x2, y2 = map(int, panel_box["xyxy"])
        panel_roi = sharpest_frame[y1:y2, x1:x2]

        if panel_roi is None or panel_roi.size == 0:
            return {
                "type": "panel",
                "status": "not_found",
                "sharpness": best_score,
                "message": "제어판 ROI가 비어 있음",
            }

        # 2. panel 전용 YOLO 로드
        _load_panel_model_once()

        # 3. Panel YOLO로 LED/온도 분석
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
                        "confidence": conf,
                    }

                elif "temp" in cls_lower or "temperature" in cls_lower:
                    t = ocr_temperature(roi)
                    if t is not None:
                        temp = t

        # 4. 이상 판단
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
                "temp": temp,
            },
        }

    except Exception as e:
        logger.exception(f"[panel] 분석 오류: {e}")
        return {
            "type": "panel",
            "status": "error",
            "message": str(e),
        }
