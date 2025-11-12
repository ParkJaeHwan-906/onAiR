"""
제어판 이상 탐지 (LED + 온도 OCR)
- sharpness 기반으로 가장 선명한 프레임 1장 선택
- Module YOLO로 제어판 ROI 추출
- Panel YOLO로 LED/온도 분석
- Flicker Voting 제거, 단일 프레임 분석으로 속도 개선
"""

import os
import cv2
import pytesseract
import numpy as np
# from ultralytics import YOLO
from loguru import logger

# ---------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_MODEL_PATH = os.path.join(BASE_DIR, "../../../models/module_best.pt")
PANEL_MODEL_PATH = os.path.join(BASE_DIR, "../../../models/panel_best.pt")

# ---------------------------------------------------------
# 하이퍼파라미터
# ---------------------------------------------------------
MIN_SHARPNESS = 70.0  # 흐린 프레임 필터링 기준


# ---------------------------------------------------------
# 유틸 함수
# ---------------------------------------------------------
def calc_sharpness(frame):
    """Laplacian variance 기반 선명도 계산"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def led_color_status(roi):
    """HSV 색상 기반 LED 상태 추정"""
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
    """Tesseract OCR로 숫자 인식"""
    roi = cv2.resize(roi, None, fx=3.0, fy=3.0)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789."
    text = pytesseract.image_to_string(thresh, config=config).strip()
    try:
        return float(text)
    except Exception:
        return None


# ---------------------------------------------------------
# 제어판 이상 탐지 (sharpest frame 기반)
# ---------------------------------------------------------
async def analyze_panel(frames):
    """
    제어판 이상 탐지 (sharpest 1장 YOLO 기반)
    """
    try:
        if not frames:
            return {"type": "panel", "status": "unknown", "message": "입력 프레임 없음"}

        # 1️⃣ sharpness 계산 및 필터링
        sharpness_scores = [calc_sharpness(f) for f in frames]
        valid_frames = [(f, s) for f, s in zip(frames, sharpness_scores) if s > MIN_SHARPNESS]
        if not valid_frames:
            return {"type": "panel", "status": "low_confidence", "message": "모든 프레임이 흐림"}

        # 2️⃣ 가장 선명한 프레임 선택
        sharpest_frame, best_score = max(valid_frames, key=lambda x: x[1])

        logger.warning("⚠️ [panel] 테스트 모드: YOLO 기반 제어판 분석 생략")
        # module_model = YOLO(MODULE_MODEL_PATH)
        # panel_model = YOLO(PANEL_MODEL_PATH)

        # module_results = module_model.predict(sharpest_frame, conf=0.5, device="cpu", verbose=False)
        # panel_roi = None
        # for r in module_results:
        #     for box in r.boxes:
        #         cls = module_model.names[int(box.cls)]
        #         if "panel" in cls.lower():
        #             x1, y1, x2, y2 = map(int, box.xyxy[0])
        #             panel_roi = sharpest_frame[y1:y2, x1:x2]
        #             break
        # if panel_roi is None or panel_roi.size == 0:
        #     return {"type": "panel", "status": "not_found", "message": "제어판 미검출"}

        # button_results = panel_model.predict(panel_roi, conf=0.5, device="cpu", verbose=False)
        # led_status, temp_values = {}, []

        # for r in button_results:
        #     for box in r.boxes:
        #         cls = panel_model.names[int(box.cls)]
        #         x1, y1, x2, y2 = map(int, box.xyxy[0])
        #         roi = panel_roi[y1:y2, x1:x2]
        #         if roi.size == 0:
        #             continue

        #         if cls == "temperature":
        #             temp = ocr_temperature(roi)
        #             if temp is not None:
        #                 temp_values.append(temp)
        #         else:
        #             on, color = led_color_status(roi)
        #             led_status[cls] = {"on": on, "color": color}

        # if not led_status and not temp_values:
        #     return {"type": "panel", "status": "low_confidence", "message": "LED/온도 인식 실패"}

        # temp_mean = np.mean(temp_values) if temp_values else None
        # msg = "정상"
        # if any(v["color"] == "red" and v["on"] for v in led_status.values()):
        #     msg = "⚠️ 경고등 점등"
        # elif temp_mean and temp_mean > 60:
        #     msg = f"⚠️ 온도 이상 ({temp_mean:.1f}°C)"

        # logger.info(f"[panel] Sharpness={best_score:.2f}, Temp={temp_mean}, LEDs={led_status}")

        return {
            "type": "panel",
            "status": "disabled",
            "sharpness": best_score,
            "message": "YOLO 기반 제어판 분석이 테스트 모드로 비활성화되었습니다",
            "results": {
                "temp": None,
                "leds": {}
            }
        }

    except Exception as e:
        logger.exception(f"[panel] 분석 중 오류: {e}")
        return {"type": "panel", "status": "error", "message": str(e)}
