import os
import cv2
import numpy as np
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "../../../models/module_best.pt")

# -------------------------------
# 게이지 각도 계산
# -------------------------------
def detect_gauge_value_fast(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, 1, 200,
        param1=100, param2=22, minRadius=50, maxRadius=0
    )
    if circles is None:
        return None, None

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

    if len(scores) == 0:
        return None, None

    angle = np.rad2deg(thetas[np.argmax(scores)]) % 360
    return angle, None


def judge_abnormal(sensor_type, value):
    if sensor_type == "thermometer":
        if value > 80: return "온도 과열 경고", "high"
        if value < 5: return "온도 너무 낮음", "low"
        return "정상", "normal"
    elif sensor_type == "pressure_gauge":
        if value > 1.5: return "압력 과다", "high"
        if value < 0.2: return "압력 부족", "low"
        return "정상", "normal"
    return "Unknown type", "unknown"


# -------------------------------
# 다프레임 voting 게이지 이상 탐지
# -------------------------------
async def analyze_gauge(frames):
    """게이지 이상 탐지 (3~5프레임 voting 기반)"""
    if not frames:
        return {"type": "gauge", "status": "unknown", "message": "프레임 없음"}

    model = YOLO(MODEL_PATH)
    outputs = []
    frame_samples = frames[-5:] if len(frames) > 5 else frames

    for frame in frame_samples:
        results = model.predict(frame, conf=0.5, device="cpu", verbose=False)
        for box in results[0].boxes:
            cls = model.names[int(box.cls)]
            if cls not in ["thermometer", "pressure_gauge"]:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            crop = frame[y1:y2, x1:x2]
            h, w = crop.shape[:2]
            if max(h, w) < 120:
                continue
            angle, _ = detect_gauge_value_fast(crop)
            if angle is not None:
                outputs.append((cls, angle))

    if not outputs:
        return {"type": "gauge", "status": "low_confidence", "message": "게이지 탐지 실패"}

    # class별 voting 처리
    result_by_type = {}
    for cls in set(c for c, _ in outputs):
        angles = [a for c, a in outputs if c == cls]
        if len(angles) < 2:
            result_by_type[cls] = {"status": "low_confidence", "message": "데이터 부족"}
            continue
        std = np.std(angles)
        mean_angle = np.mean(angles)
        if std > 10:
            result_by_type[cls] = {"status": "low_confidence", "message": f"편차 과다 (std={std:.2f})"}
            continue

        # 각도 → 값 변환
        ratio = (mean_angle - 230) / 90
        value = np.clip(ratio * (100 if cls == "thermometer" else 2), 0, None)
        msg, status = judge_abnormal(cls, value)
        result_by_type[cls] = {"angle": mean_angle, "value": value, "status": status, "message": msg}

    return {"type": "gauge", "status": "done", "results": result_by_type}
