import cv2
import numpy as np
from loguru import logger

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
        h, w = roi.shape[:2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # -----------------------
        # 1) 중심 + 반지름 추정
        # -----------------------
        circles = cv2.HoughCircles(
            blur, cv2.HOUGH_GRADIENT, 1, 200,
            param1=100, param2=22, minRadius=50, maxRadius=0
        )

        img_center = np.array([w / 2, h / 2])

        if circles is None:
            x0, y0 = w // 2, h // 2
            R = max(min(h, w) * 0.45, 20)
        else:
            circles = np.uint16(np.around(circles))[0]
            x0, y0, R = max(
                circles,
                key=lambda c: (c[2] * 0.7)
                - np.linalg.norm(np.array([c[0], c[1]]) - img_center)
            )
            R = max(min(R, min(h, w) * 0.45), 20)

        # -----------------------
        # 2) Edge + 바늘 몸통 mask
        # -----------------------
        edges = cv2.Canny(blur, 50, 150)

        yy, xx = np.indices(edges.shape)
        rr = np.sqrt((xx - x0) ** 2 + (yy - y0) ** 2)

        pointer_mask = (rr > R * 0.20) & (rr < R * 0.60)
        edges_ptr = edges.copy()
        edges_ptr[~pointer_mask] = 0

        # fallback
        if edges_ptr.sum() < 400:
            edges_ptr = edges

        # -----------------------
        # 3) Angle voting
        # -----------------------
        thetas = np.deg2rad(np.arange(0, 360, 1.5))
        scores = []

        for th in thetas:
            xs = (x0 + np.cos(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
            ys = (y0 - np.sin(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
            xs = np.clip(xs, 0, w - 1)
            ys = np.clip(ys, 0, h - 1)
            scores.append(edges_ptr[ys, xs].sum())

        scores = np.asarray(scores, dtype=np.float32)
        if scores.max() < 10:
            return None

        degs = (np.rad2deg(thetas) + 180) % 360

        # -----------------------
        # 4) valid range filtering
        # -----------------------
        def cw(a, b): return (a - b) % 360

        min_angle = cfg["min_angle"]
        max_angle = cfg["max_angle"]
        sweep = cw(min_angle, max_angle) or 360

        margin = 5.0
        valid_mask = []
        for d in degs:
            prog = cw(min_angle, d)
            valid_mask.append(prog <= (sweep + margin))
        valid_mask = np.array(valid_mask, bool)
        scores[~valid_mask] = 0

        best_idx = int(np.argmax(scores))
        angle = float(degs[best_idx] % 360)

        # -----------------------
        # 5) 몸통 두께 기반 flip correction
        # -----------------------
        def body_thickness(a):
            th = np.deg2rad(a)
            rs = np.linspace(R * 0.20, R * 0.45, 15)
            widths = []

            for r in rs:
                x = int(x0 + np.cos(th) * r)
                y = int(y0 - np.sin(th) * r)

                line_vals = []
                for k in range(-7, 8):
                    xx = int(x - k * np.sin(th))
                    yy = int(y + k * np.cos(th))

                    if 0 <= xx < w and 0 <= yy < h:
                        line_vals.append(edges[yy, xx])
                    else:
                        line_vals.append(0)

                widths.append(sum(v > 0 for v in line_vals))

            return np.mean(widths)

        opp = (angle + 180) % 360
        if body_thickness(opp) > body_thickness(angle) * 1.15:
            angle = opp

        # -----------------------
        # 6) thermometer 전용 물리 보정
        # -----------------------
        def cw_delta(a, b):
            return (a - b) % 360

        angle = float(angle)

        # 1) 기본값 계산
        progressed = cw_delta(min_angle, angle)
        ratio = float(np.clip(progressed / sweep, 0, 1))
        value = cfg["min_val"] + ratio * (cfg["max_val"] - cfg["min_val"])

        # 2) 반대각 계산 (항상 계산해둔다)
        opp_angle = (angle + 180) % 360
        prog_o = cw_delta(min_angle, opp_angle)
        ratio_o = float(np.clip(prog_o / sweep, 0, 1))
        value_o = cfg["min_val"] + ratio_o * (cfg["max_val"] - cfg["min_val"])

        # ------------------------------------------------
        # 3) 강제 보정(Override) 조건
        # ------------------------------------------------
        # thermometer처럼 0~100 범위인 경우만 적용
        if cfg["max_val"] == 100:

            # 누가 봐도 반대인 상황 강제 보정
            if value <= 20 or value >= 80:
                angle = opp_angle
                value = value_o

        return angle, value
    except:
        return None


# -------------------------------------
# ABNORMAL JUDGE
# -------------------------------------
def judge_abnormal(gauge_type, value):
    gauge_type = gauge_type.lower()

    if "thermometer" in gauge_type or "thermo" in gauge_type:
        if value > 40:
            return "온도 과열", "thermo_high"
        if value < 20:
            return "온도 과열", "thermo_high"
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
