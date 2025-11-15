import cv2
import numpy as np
from loguru import logger

# sharpness threshold
MIN_SHARPNESS = 70.0

# gauge config
THERMO_CONFIG = {
    "min_angle": 240,
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


def calc_sharpness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


# -------------------------------------
# FAST GAUGE ANGLE + VALUE
# -------------------------------------
def detect_gauge_angle_fast(roi, cfg):
    h, w = roi.shape[:2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

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
            key=lambda c: (c[2] * 0.7) - np.linalg.norm(np.array([c[0], c[1]]) - img_center)
        )

    edges = cv2.Canny(blur, 50, 150)
    yy, xx = np.indices(edges.shape)
    rr = np.sqrt((xx - x0) ** 2 + (yy - y0) ** 2)

    mask_annulus = (rr > R * 0.20) & (rr < R * 0.90)
    mask_textband = (rr > R * 0.50) & (rr < R * 0.70)
    edges[~mask_annulus] = 0
    edges[mask_textband] = 0

    thetas = np.deg2rad(np.arange(0, 360, 2.0))
    scores = []

    for th in thetas:
        xs = (x0 + np.cos(th) * np.linspace(R * 0.25, R * 0.90, 60)).astype(int)
        ys = (x0 - np.sin(th) * np.linspace(R * 0.25, R * 0.90, 60)).astype(int)
        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)
        scores.append(edges[ys, xs].sum())

    if not scores:
        return None

    best_idx = int(np.argmax(scores))
    angle = (np.rad2deg(thetas[best_idx]) + 360) % 360

    # 반전 체크
    opp_angle = (angle + 180) % 360

    xs1 = (x0 + np.cos(np.deg2rad(angle)) * np.linspace(R * 0.30, R * 0.90, 30)).astype(int)
    ys1 = (y0 - np.sin(np.deg2rad(angle)) * np.linspace(R * 0.30, R * 0.90, 30)).astype(int)

    xs2 = (x0 + np.cos(np.deg2rad(opp_angle)) * np.linspace(R * 0.30, R * 0.90, 30)).astype(int)
    ys2 = (y0 - np.sin(np.deg2rad(opp_angle)) * np.linspace(R * 0.30, R * 0.90, 30)).astype(int)

    score1 = edges[ys1, xs1].sum()
    score2 = edges[ys2, xs2].sum()

    if score2 > score1 * 1.15:
        angle = opp_angle

    # 각도 → 값 변환
    def cw_delta(a, b): return (a - b) % 360

    sweep_cw = cw_delta(cfg["min_angle"], cfg["max_angle"])
    if sweep_cw == 0:
        sweep_cw = 360

    progressed = cw_delta(cfg["min_angle"], angle)
    ratio = float(np.clip(progressed / sweep_cw, 0, 1))

    value = cfg["min_val"] + ratio * (cfg["max_val"] - cfg["min_val"])

    return angle, value


# -------------------------------------
# JUDGE ABNORMAL
# -------------------------------------
def judge_abnormal(gauge_type, value):
    gauge_type = gauge_type.lower()

    if "thermometer" in gauge_type:
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

    return "Unknown type", "unknown"


# -------------------------------------
# MAIN ENTRY
# -------------------------------------
async def analyze_gauge(sharpest_frame, best_score, module_boxes):
    try:
        # 후보 gauge 필터링
        gauge_boxes = [
            b for b in module_boxes
            if any(k in b["label"].lower() for k in ["gauge", "thermo", "pressure"])
        ]

        if not gauge_boxes:
            return {
                "type": "gauge",
                "status": "not_found",
                "detail": None,
                "sharpness": best_score,
                "results": {},
                "message": "게이지 미검출"
            }

        results = {}
        found_anomaly = False
        final_detail = None
        final_message = "정상"

        for box in gauge_boxes:
            x1, y1, x2, y2 = box["xyxy"]
            roi = sharpest_frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            label = box["label"].lower()

            # config 결정
            if "thermo" in label:
                cfg = THERMO_CONFIG
            elif "pressure" in label:
                cfg = PRESS_CONFIG
            else:
                continue

            angle_val = detect_gauge_angle_fast(roi, cfg)
            if angle_val is None:
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
                # RAG-friendly 자연 문장
                final_message = f"{msg}. 현재 측정값: {value:.2f}"

        return {
            "type": "gauge",
            "status": "anomaly" if found_anomaly else "normal",
            "detail": final_detail,
            "sharpness": best_score,
            "results": results,
            "message": final_message
        }

    except Exception as e:
        logger.exception(f"[gauge] 오류: {e}")
        return {
            "type": "gauge",
            "status": "error",
            "detail": "exception",
            "message": str(e)
        }
