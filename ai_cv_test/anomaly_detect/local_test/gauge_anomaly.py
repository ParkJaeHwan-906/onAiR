import cv2
import numpy as np
from loguru import logger

THERMO_CONFIG = {
    "min_angle": 230,
    "max_angle": 330,
    "min_val": 0,
    "max_val": 100
}

PRESS_CONFIG = {
    "min_angle": 210,
    "max_angle": 330,
    "min_val": 0,
    "max_val": 2.0
}

# -----------------------------
# RAG-friendly 메시지 매핑
# -----------------------------
GAUGE_RAG_MESSAGE = {
    "normal": "게이지는 정상 범위입니다.",
    "thermo_high": "온도계의 온도가 비정상적으로 높습니다.",
    "thermo_low": "온도계의 온도가 비정상적으로 낮습니다.",
    "pressure_high": "압력계의 압력이 허용 범위를 초과했습니다.",
    "pressure_low": "압력계의 압력이 허용 범위보다 낮습니다.",
    "no_frame": "프레임을 가져오지 못해 게이지 상태를 분석할 수 없습니다.",
    "not_found": "게이지가 탐지되지 않았습니다.",
    "exception": "게이지 분석 중 오류가 발생했습니다.",
    "unknown": "게이지 종류를 판단할 수 없습니다."
}

# -------------------------------------
# FAST GAUGE ANGLE + VALUE
# -------------------------------------
import cv2
import numpy as np
import os
from ultralytics import YOLO


# gauge config
THERMO_CFG = dict(min_angle=230, max_angle=330, min_val=0, max_val=100)
PRESS_CFG  = dict(min_angle=210, max_angle=330, min_val=0, max_val=2)


# ===============================================
#   유일한 gauge detection 함수 (fast 버전 통합)
# ===============================================
def detect_gauge_fast(
    img,
    min_angle,
    max_angle,
    min_value,
    max_value,
    resize_limit=400
):

    if img is None or img.size == 0:
        return None, None

    img = img.copy()
    h, w = img.shape[:2]

    # resize (fast 버전과 동일)
    scale = resize_limit / max(h, w) if max(h, w) > resize_limit else 1.0
    if scale < 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]

    # preprocess
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # circle detection
    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, 1, 200,
        param1=100, param2=22,
        minRadius=50, maxRadius=0
    )

    img_center = np.array([w / 2, h / 2])

    if circles is None:
        x0, y0 = w // 2, h // 2
        R = min(h, w) // 2 - 40
    else:
        circles = np.uint16(np.around(circles))[0]
        x0, y0, R = max(
            circles,
            key=lambda c: (c[2] * 0.7)
            - np.linalg.norm(np.array([c[0], c[1]]) - img_center)
        )

    # edge + mask
    edges = cv2.Canny(blur, 50, 150)
    yy, xx = np.indices(edges.shape)
    rr = np.sqrt((xx - x0)**2 + (yy - y0)**2)

    mask_annulus = (rr > R * 0.20) & (rr < R * 0.90)
    mask_textband = (rr > R * 0.50) & (rr < R * 0.70)

    edges[~mask_annulus] = 0
    edges[mask_textband] = 0

    # angle voting (fast 버전 그대로)
    thetas = np.deg2rad(np.arange(0, 360, 2.0))
    scores = []

    for th in thetas:
        xs = (x0 + np.cos(th) * np.linspace(R * 0.25, R * 0.90, 60)).astype(int)
        ys = (y0 - np.sin(th) * np.linspace(R * 0.25, R * 0.90, 60)).astype(int)

        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)
        scores.append(edges[ys, xs].sum())

    if len(scores) == 0:
        return None, None

    best_idx = int(np.argmax(scores))
    angle = (np.rad2deg(thetas[best_idx]) + 360) % 360

    # fast 버전과 동일
    angle = (angle + 180) % 360
    opp_angle = (angle + 180) % 360

    xs1 = (x0 + np.cos(np.deg2rad(angle)) * np.linspace(R * 0.30, R * 0.90, 30)).astype(int)
    ys1 = (y0 - np.sin(np.deg2rad(angle)) * np.linspace(R * 0.30, R * 0.90, 30)).astype(int)
    xs2 = (x0 + np.cos(np.deg2rad(opp_angle)) * np.linspace(R * 0.30, R * 0.90, 30)).astype(int)
    ys2 = (y0 - np.sin(np.deg2rad(opp_angle)) * np.linspace(R * 0.30, R * 0.90, 30)).astype(int)

    score1 = edges[ys1, xs1].sum()
    score2 = edges[ys2, xs2].sum()

    if score2 > score1 * 1.15:
        angle = opp_angle

    # angle → value
    def cw_delta(a, b):
        return (a - b) % 360

    sweep_cw = cw_delta(min_angle, max_angle)
    if sweep_cw == 0:
        sweep_cw = 360

    progressed = cw_delta(min_angle, angle)
    ratio = float(np.clip(progressed / sweep_cw, 0, 1))

    value = min_value + ratio * (max_value - min_value)
    return angle, value


# ===============================================
#             이상 판단 (fast 버전 그대로)
# ===============================================
def judge_abnormal(sensor_type, value):
    if sensor_type == "thermometer":
        if value > 80: return "온도 과열", "high"
        if value < 5:  return "온도 너무 낮음", "low"
        return "정상", "normal"

    if sensor_type == "pressure_gauge":
        if value > 1.5: return "압력 과다", "high"
        if value < 0.2: return "압력 부족", "low"
        return "정상", "normal"

    return "Unknown", "unknown"


# ======================================================
#           YOLO + gauge detection (fast버전 사용)
# ======================================================
def analyze_module_gauges(image_path):
    model = YOLO("models/all.pt")
    results = model.predict(image_path, conf=0.4, device="cpu", verbose=False)

    img = cv2.imread(image_path)

    if len(results[0].boxes) == 0:
        print("❌ YOLO 탐지 결과 없음 (게이지 미검출)")
        return

    found = False

    for box in results[0].boxes:
        cls = model.names[int(box.cls)]
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        if cls not in ["thermometer", "pressure_gauge"]:
            continue

        found = True

        crop = img[y1:y2, x1:x2]
        cfg = THERMO_CFG if cls == "thermometer" else PRESS_CFG
  
        angle, value = detect_gauge_fast(
            crop,
            cfg["min_angle"],
            cfg["max_angle"],
            cfg["min_val"],
            cfg["max_val"]
        )

        if angle is not None:
            msg, status = judge_abnormal(cls, value)
            print(f"{cls}: {value:.2f} → {msg}")
        else:
            print(f"{cls}: 지침 인식 실패")

    if not found:
        print("❌ thermometer / pressure_gauge 클래스 미검출")






# -------------------------------------
# ABNORMAL JUDGE
# -------------------------------------
def judge_abnormal(gauge_type, value):
    gauge_type = gauge_type.lower()

    if "thermometer" in gauge_type or "thermo" in gauge_type:
        if value > 80:
            return "온도 과열", "thermo_high"
        if value < 5:
            return "온도 너무 낮음", "thermo_low"
        return "정상", "normal"

    if "pressure" in gauge_type:
        if value > 1.5:
            return "압력 과다", "pressure_high"
        if value < 0.2:
            return "압력 부족", "pressure_low"
        return "정상", "normal"

    return "Unknown", "unknown"


# -------------------------------------
# MAIN ENTRY (NEW STRUCTURE)
# -------------------------------------
async def analyze_gauge(frame, gauge_boxes):
    try:
        if frame is None:
            return {
                "type": "gauge",
                "status": "error",
                "detail": "no_frame",
                "message": "프레임 없음",
                "results": {}
            }

        if not gauge_boxes:
            return {
                "type": "gauge",
                "status": "not_found",
                "detail": None,
                "message": "게이지 미검출",
                "results": {}
            }

        results = {}
        found_anomaly = False
        final_detail = None
        final_message = "정상"

        for box in gauge_boxes:
            x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
            roi = frame[y1:y2, x1:x2]

            if roi is None or roi.size == 0:
                continue

            label = box["label"].lower()

            # config 결정
            if "thermo" in label or "temperature" in label:
                cfg = THERMO_CONFIG
            elif "pressure" in label:
                cfg = PRESS_CONFIG
            else:
                continue

            angle_val = detect_gauge_fast(
                roi,
                cfg["min_angle"],
                cfg["max_angle"],
                cfg["min_val"],
                cfg["max_val"]
            )
            if angle_val is None:
                results[box["label"]] = {
                    "angle": None,
                    "value": None,
                    "status": "no_detection",
                    "message": "지침 검출 실패"
                }
                continue

            angle, value = angle_val
            msg, detail_code = judge_abnormal(label, value)

            results[box["label"]] = {
                "angle": float(angle),
                "value": float(value),
                "status": "anomaly" if detail_code != "normal" else "normal",
                "message": msg
            }

            if detail_code != "normal":
                found_anomaly = True
                final_detail = detail_code
                final_message = f"{msg}. 현재 측정값: {value:.2f}"
        if all(r["status"] == "no_detection" for r in results.values()):
            return {
                "type": "gauge",
                "status": "no_detection",
                "detail": "no_detection",
                "message": "게이지는 있으나 지침 검출 실패",
                "results": results
            }

        return {
            "type": "gauge",
            "status": "anomaly" if found_anomaly else "normal",
            "detail": final_detail,
            "results": results,
            "message": final_message
        }

    except Exception as e:
        logger.exception(f"[gauge] error: {e}")
        return {
            "type": "gauge",
            "status": "error",
            "detail": "exception",
            "message": str(e),
            "results": {}
        }

if __name__ == "__main__":
    analyze_module_gauges("samples/thermometer.png")

