import cv2
import numpy as np
from loguru import logger

# RAG-friendly 메시지 매핑
PANEL_RAG_MESSAGE = {
    "normal": "제어판은 정상 상태입니다",
    "overheat": "제어판에서 과열 경고가 감지되었습니다",
    "power_off": "제어판 전원이 꺼져 있거나 전원 LED가 꺼져 있습니다",
    "temp_high": "제어판 온도가 비정상적으로 높습니다",
    "no_frame": "입력 프레임이 없어 제어판 상태를 분석하지 못했습니다",
    "panel_not_found": "제어판 박스를 찾지 못했습니다",
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


def detect_abnormal(led_status):
    if led_status.get("overheat_light", {}).get("on", False):
        return "overheat"
    if not led_status.get("power_light", {}).get("on", True):
        return "power_off"
    return "normal"


# 메인: panel 분석
async def analyze_panel(frame, panel_boxes, part_boxes):
    try:
        if frame is None:
            detail = "no_frame"
            return {
                "type": "panel",
                "status": "unknown",
                "detail": detail,
                "message": PANEL_RAG_MESSAGE.get(detail),
                "results": {}
            }

        # panel box가 단 하나라고 전제 (이미 anomaly.py에서 max_confidence로 선택됨)
        if not panel_boxes:
            detail = "panel_not_found"
            return {
                "type": "panel",
                "status": "not_found",
                "detail": detail,
                "message": PANEL_RAG_MESSAGE.get(detail),
                "results": {}
            }

        panel_box = panel_boxes[0]

        x1, y1, x2, y2 = panel_box["x1"], panel_box["y1"], panel_box["x2"], panel_box["y2"]
        panel_roi = frame[y1:y2, x1:x2]

        if panel_roi is None or panel_roi.size == 0:
            detail = "empty_roi"
            return {
                "type": "panel",
                "status": "not_found",
                "detail": detail,
                "message": PANEL_RAG_MESSAGE.get(detail),
                "results": {}
            }

        led_status = {}

        for part in part_boxes:
            px1, py1, px2, py2 = part["x1"], part["y1"], part["x2"], part["y2"]
            roi = frame[py1:py2, px1:px2]

            if roi is None or roi.size == 0:
                continue

            name = part["label"]

            # LED/버튼류만 분석
            is_on, color, ratios = led_color_status(roi)

            led_status[name] = {
                "on": is_on,
                "color": color,
                "ratios": ratios,
                "confidence": part["confidence"]
            }

        anomaly = detect_abnormal(led_status)

        return {
            "type": "panel",
            "status": "anomaly" if anomaly != "normal" else "normal",
            "detail": anomaly,
            "message": PANEL_RAG_MESSAGE.get(anomaly, "판단 불가"),
            "results": {
                "leds": led_status
            }
        }

    except Exception as e:
        logger.exception(f"[panel] error: {e}")
        detail = "exception"
        return {
            "type": "panel",
            "status": "error",
            "detail": detail,
            "message": PANEL_RAG_MESSAGE.get(detail),
            "results": {}
        }
