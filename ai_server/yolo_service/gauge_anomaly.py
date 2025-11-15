import cv2
import numpy as np
from loguru import logger

MIN_SHARPNESS = 70.0


def calc_sharpness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def detect_gauge_angle(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        1,
        200,
        param1=100,
        param2=22,
        minRadius=50,
        maxRadius=0,
    )
    if circles is None:
        return None

    x0, y0, R = np.uint16(np.around(circles[0][0]))
    edges = cv2.Canny(blur, 50, 150)
    h, w = gray.shape

    thetas = np.deg2rad(np.arange(0, 360, 2))
    scores = []

    for th in thetas:
        xs = (x0 + np.cos(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
        ys = (y0 - np.sin(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)
        scores.append(edges[ys, xs].sum())

    if not scores:
        return None

    angle = np.rad2deg(thetas[np.argmax(scores)]) % 360
    return angle


def judge_abnormal(gauge_type, value):
    if "thermometer" in gauge_type.lower():
        if value > 80:
            return "온도 과열", "high"
        if value < 5:
            return "온도 너무 낮음", "low"
        return "정상", "normal"

    if "pressure" in gauge_type.lower():
        if value > 1.5:
            return "압력 과다", "high"
        if value < 0.2:
            return "압력 부족", "low"
        return "정상", "normal"

    return "Unknown type", "unknown"


async def analyze_gauge(sharpest_frame, best_score, module_boxes):
    try:
        # module_boxes: [{"label", "xyxy", "conf"}, ...]

        # gauge류 박스만 추림
        gauge_boxes = [
            b for b in module_boxes
            if any(k in b["label"].lower() for k in ["gauge", "thermometer", "pressure"])
        ]

        if not gauge_boxes:
            return {
                "type": "gauge",
                "status": "not_found",
                "sharpness": best_score,
                "message": "게이지 미검출"
            }

        final_results = {}
        found_anomaly = False

        for box in gauge_boxes:
            x1, y1, x2, y2 = box["xyxy"]
            roi = sharpest_frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            angle = detect_gauge_angle(roi)
            if angle is None:
                continue

            if "thermometer" in box["label"].lower():
                value = (angle / 360.0) * 100
            elif "pressure" in box["label"].lower():
                value = (angle / 360.0) * 2.0
            else:
                value = angle / 360.0

            msg, status = judge_abnormal(box["label"], value)

            final_results[box["label"]] = {
                "value": float(value),
                "angle": float(angle),
                "status": status,
                "message": msg
            }

            if status != "normal":
                found_anomaly = True

        return {
            "type": "gauge",
            "status": "anomaly" if found_anomaly else "normal",
            "sharpness": best_score,
            "results": final_results,
            "message": "이상 탐지됨" if found_anomaly else "정상"
        }

    except Exception as e:
        logger.exception(f"[gauge] 오류: {e}")
        return {"type": "gauge", "status": "error", "message": str(e)}
