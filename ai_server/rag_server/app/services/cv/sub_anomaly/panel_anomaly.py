"""
제어판 이상 탐지 (YOLO 서비스 연동)
- sharpness 기반으로 가장 선명한 프레임 1장 선택
- YOLO 서비스(Module/Panels) 결과를 활용해 LED/온도 분석
"""

import cv2
import numpy as np
import pytesseract
from loguru import logger

from app.services.cv.yolo_client import YOLOServiceError, infer_module, infer_panel
from app.services.cv.utils import calc_sharpness, select_sharpest_frame

MIN_SHARPNESS = 70.0  # 흐린 프레임 필터링 기준


def led_color_status(roi):
    """HSV 색상 기반 LED 상태 추정"""
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


async def analyze_panel(
    frames,
):
    """
    제어판 이상 탐지 (sharpest 1장 YOLO 기반)
    """
    try:
        if not frames:
            return {"type": "panel", "status": "unknown", "message": "입력 프레임 없음"}

        # 최신 3장만 사용
        frames_to_use = frames[-3:] if len(frames) >= 3 else frames
        # sharpness 기반 filtering & 최고 선명 프레임 추출
        sharpness_scores = [calc_sharpness(f) for f in frames_to_use]
        valid_pairs = [(f, s) for f, s in zip(frames_to_use, sharpness_scores) if s > MIN_SHARPNESS]
        if not valid_pairs:
            return {"type": "panel", "status": "low_confidence", "message": "모든 프레임이 흐림"}

        valid_frames = [f for f, _ in valid_pairs]
        sharpest_frame = select_sharpest_frame(valid_frames)
        best_score = calc_sharpness(sharpest_frame)

        module_resp = await infer_module([sharpest_frame])
        module_dets = module_resp.get("frames", [[]])[0] if module_resp.get("frames") else []

        panel_box = None
        for det in module_dets:
            if "panel" in det.get("label", "").lower():
                panel_box = det.get("box")
                break

        if not panel_box:
            return {
                "type": "panel",
                "status": "not_found",
                "sharpness": best_score,
                "message": "제어판 미검출",
            }

        x1, y1, x2, y2 = [int(v) for v in panel_box]
        panel_roi = sharpest_frame[y1:y2, x1:x2]
        if panel_roi.size == 0:
            return {
                "type": "panel",
                "status": "not_found",
                "sharpness": best_score,
                "message": "제어판 ROI가 비어있습니다",
            }

        panel_resp = await infer_panel(panel_roi)
        panel_dets = panel_resp.get("detections", [])

        leds = {}
        temp = None

        for det in panel_dets:
            label = det.get("label", "")
            conf = float(det.get("confidence", 0.0))
            box = det.get("box", None)
            if not box:
                continue

            px1, py1, px2, py2 = [int(v) for v in box]
            roi = panel_roi[py1:py2, px1:px2]
            if roi.size == 0:
                continue

            label_lower = label.lower()

            if "led" in label_lower or "button" in label_lower:
                is_on, color = led_color_status(roi)
                leds[label] = {"status": "on" if is_on else "off", "color": color, "confidence": conf}
            elif "temp" in label_lower or "temperature" in label_lower:
                temp_value = ocr_temperature(roi)
                if temp_value is not None:
                    temp = temp_value

        has_anomaly = False
        if temp is not None and (temp > 80 or temp < 5):
            has_anomaly = True

        for led_info in leds.values():
            if led_info["status"] == "on" and led_info["color"] == "red":
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

    except YOLOServiceError as err:
        logger.warning(f"[panel] YOLO 서비스 오류: {err.code} ({err.message})")
        return {"type": "panel", "status": "error", "message": err.message}
    except Exception as e:  # pragma: no cover
        logger.exception(f"[panel] 분석 중 오류: {e}")
        return {"type": "panel", "status": "error", "message": str(e)}
