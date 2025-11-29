import cv2
import numpy as np
from loguru import logger

# gauge config
THERMO_CONFIG = {
    "min_angle": 225,
    "max_angle": 315,
    "min_val": 0,
    "max_val": 100
}

PRESS_CONFIG = {
    "min_angle": 230,
    "max_angle": 325,
    "min_val": 0,
    "max_val": 1.5
}


def cw_delta(a, b):
    return (a - b) % 360


# -----------------------------
# ROI normalize (고정 크기)
# -----------------------------
def normalize_roi(roi):
    return cv2.resize(roi, (300, 300))


# -----------------------------
# 단순 허브 중심 추정 (ROI 중심)
# -----------------------------
def detect_center_hub_new(img):
    h, w = img.shape[:2]
    cx = w // 2
    cy = h // 2
    return cx, cy


# -----------------------------
# 기존 big radius 대신 개선된 버전
# -----------------------------
def detect_big_radius(img, cx, cy, r_small):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)
    edges = cv2.Canny(blur, 40, 120)

    h, w = gray.shape[:2]
    Rmin = int(min(h, w) * 0.38)
    Rmax = int(min(h, w) * 0.49)

    print(f"[DEBUG] search R range: {Rmin} ~ {Rmax}")

    thetas = range(0, 360, 2)
    distances = []

    for ang in thetas:
        th = np.deg2rad(ang)
        for r in range(Rmin, Rmax):
            x = int(cx + np.cos(th) * r)
            y = int(cy - np.sin(th) * r)

            if x < 0 or x >= w or y < 0 or y >= h:
                break

            if edges[y, x] > 0:
                distances.append(r)
                break

    if not distances:
        print("[ERROR] big circle detection failed")
        return None

    R = int(np.median(distances))
    print(f"[INFO] big R = {R}")
    return R


# -----------------------------
# 4) Dark-only angle voting
# -----------------------------
def dark_only_angle_voting(gray_img, center, R, dark_thresh=120):
    h, w = gray_img.shape
    x0, y0 = center
    scores = []

    for ang in range(360):
        theta = np.deg2rad(ang)

        rs = np.arange(0, R, 1)
        xs = (x0 + np.cos(theta) * rs).astype(int)
        ys = (y0 - np.sin(theta) * rs).astype(int)

        valid = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
        xs = xs[valid]
        ys = ys[valid]

        if len(xs) == 0:
            scores.append(0)
            continue

        dark_score = np.sum(gray_img[ys, xs] < dark_thresh)
        scores.append(dark_score)

    scores = np.array(scores)
    best_angle = int(np.argmax(scores))
    print(f"[INFO] best angle = {best_angle}°")

    return best_angle, scores


def angle_to_value(angle_deg, cfg):
    min_angle = cfg["min_angle"]
    max_angle = cfg["max_angle"]
    min_val = cfg["min_val"]
    max_val = cfg["max_val"]

    sweep = cw_delta(min_angle, max_angle)
    if sweep == 0:
        sweep = 360

    progressed = cw_delta(min_angle, angle_deg)
    ratio = np.clip(progressed / sweep, 0, 1)
    value = min_val + ratio * (max_val - min_val)
    return float(value)


def detect_center_hub(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)

    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=30,
        param1=80,
        param2=15,
        minRadius=5,
        maxRadius=35
    )

    h, w = img.shape[:2]
    cx_img, cy_img = w // 2, h // 2  # ROI 중심

    if circles is not None:
        circles = np.uint16(np.around(circles))

        best = None
        best_dist = 1e9

        for c in circles[0]:
            x, y, r = c
            dist = (x - cx_img) ** 2 + (y - cy_img) ** 2

            dx = abs(x - cx_img)
            dy = abs(y - cy_img)

            if dx < w * 0.15 and dy < h * 0.15:
                if dist < best_dist:
                    best = c
                    best_dist = dist

        if best is not None:
            cx, cy, r_small = best
            print(f"[INFO] hub detected → ({cx}, {cy}), r={r_small}")
            return cx, cy, int(r_small)

    print("[WARN] hub not found (failed 10% rule)")
    return None, None, None


def detect_center_hub_intensity(img, debug_dir=None):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)

    h, w = gray.shape

    thresh_val = np.percentile(blur, 3)
    mask = (blur <= thresh_val).astype(np.uint8) * 255

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)

    if num_labels <= 1:
        cx, cy = w // 2, h // 2
        print("[WARN] intensity hub not found → fallback to center")
        return cx, cy, None

    best_idx = None
    best_score = -1

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]

        if area < 5 or area > 500:
            continue

        cx_blob, cy_blob = centroids[i]
        dist_center = (cx_blob - w / 2) ** 2 + (cy_blob - h / 2) ** 2
        score = -dist_center

        if score > best_score:
            best_score = score
            best_idx = i

    if best_idx is None:
        cx, cy = w // 2, h // 2
        print("[WARN] hub not found (no blob) → fallback center")
        return cx, cy, None

    cx_hub, cy_hub = centroids[best_idx]
    cx_hub, cy_hub = int(cx_hub), int(cy_hub)

    ys, xs = np.where(labels == best_idx)
    dists = np.sqrt((xs - cx_hub) ** 2 + (ys - cy_hub) ** 2)
    r_small = int(np.mean(dists))

    if debug_dir:
        vis = img.copy()
        cv2.circle(vis, (cx_hub, cy_hub), 3, (0, 0, 255), -1)
        cv2.circle(vis, (cx_hub, cy_hub), r_small, (0, 255, 0), 2)
        cv2.imwrite(f"{debug_dir}/hub_intensity_detected.png", vis)

    print(f"[INFO] intensity hub detected → ({cx_hub},{cy_hub}), r={r_small}")

    return cx_hub, cy_hub, r_small


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
def detect_gauge_angle_fast(roi, cfg):
    try:
        roi = normalize_roi(roi)

        cx, cy = detect_center_hub_new(roi)
        r_small = 10

        R = detect_big_radius(roi, cx, cy, r_small)
        if R is None:
            return None

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        best_angle, scores = dark_only_angle_voting(gray, (cx, cy), R)

        value = angle_to_value(best_angle, cfg)
        logger.info(f"angle={best_angle:.2f}°, value={value:.2f}")
        return float(best_angle), float(value)

    except Exception as e:
        logger.exception(f"[gauge] fast-angle error: {e}")
        return None


# -------------------------------------
# ABNORMAL JUDGE
# -------------------------------------
def judge_abnormal(gauge_type, value):
    gauge_type = gauge_type.lower()

    if "thermometer" in gauge_type or "thermo" in gauge_type:
        if value > 40:
            return "온도 과열", "thermo_high"
        if value < 10:
            return "온도 낮음", "thermo_low"
        return "정상", "normal"

    if "pressure" in gauge_type:
        if value > 0.8:
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

            if "thermometer" in label:
                cfg = THERMO_CONFIG
            elif "pressure" in label:
                cfg = PRESS_CONFIG
            else:
                continue

            angle_val = detect_gauge_angle_fast(roi, cfg)
            if angle_val is None:
                continue

            angle, value = angle_val
            logger.info(f"[GAUGE] {label} angle={angle:.2f}°, value={value:.2f}")
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
