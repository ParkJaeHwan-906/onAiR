import cv2
import numpy as np
import os
from ultralytics import YOLO

# gauge config
THERMO_CFG = dict(min_angle=230, max_angle=330, min_val=0, max_val=100)
PRESS_CFG  = dict(min_angle=210, max_angle=330, min_val=0, max_val=2)


# ---------------------------------
# 1) 전체 게이지 중심을 1회만 검출
# ---------------------------------
def detect_gauge_center(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, 1, 200,
        param1=100, param2=22,
        minRadius=80, maxRadius=0
    )

    if circles is None:
        h, w = img.shape[:2]
        return w//2, h//2, min(w, h)//2 - 40

    circles = np.uint16(np.around(circles))[0]
    c = max(circles, key=lambda c: c[2])
    return int(c[0]), int(c[1]), int(c[2])


# ----------------------------------------
# 2) 중심 고정 + ROI 상대좌표 기반 각도 계산
# ----------------------------------------
def detect_angle_with_fixed_center(roi, cx, cy, R, cfg):
    if roi is None or roi.size == 0:
        return None, None

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    h, w = roi.shape[:2]
    yy, xx = np.indices(edges.shape)
    rr = np.sqrt((xx - cx)**2 + (yy - cy)**2)

    mask_annulus = (rr > R * 0.25) & (rr < R * 0.95)
    mask_text    = (rr > R * 0.50) & (rr < R * 0.75)

    edges[~mask_annulus] = 0
    edges[mask_text] = 0

    thetas = np.deg2rad(np.arange(0, 360, 2))
    scores = []

    for th in thetas:
        xs = (cx + np.cos(th) * np.linspace(R*0.25, R*0.9, 60)).astype(int)
        ys = (cy - np.sin(th) * np.linspace(R*0.25, R*0.9, 60)).astype(int)

        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)
        scores.append(edges[ys, xs].sum())

    if max(scores) == 0:
        return None, None

    angle = (np.rad2deg(thetas[int(np.argmax(scores))]) + 360) % 360
    angle = (angle + 180) % 360
    opp   = (angle + 180) % 360

    def score_dir(a):
        xs = (cx + np.cos(np.deg2rad(a)) * np.linspace(R*0.3, R*0.9, 30)).astype(int)
        ys = (cy - np.sin(np.deg2rad(a)) * np.linspace(R*0.3, R*0.9, 30)).astype(int)
        return edges[ys, xs].sum()

    if score_dir(opp) > score_dir(angle) * 1.15:
        angle = opp

    def cw(a, b): return (a - b) % 360

    sweep = cw(cfg["min_angle"], cfg["max_angle"])
    sweep = 360 if sweep == 0 else sweep

    prog = cw(cfg["min_angle"], angle)
    ratio = float(np.clip(prog / sweep, 0, 1))

    value = cfg["min_val"] + ratio * (cfg["max_val"] - cfg["min_val"])

    return angle, value

def detect_gauge_value_fast(img_path, min_angle, max_angle, min_value, max_value, resize_limit=380):
    img = cv2.imread(img_path)
    if img is None:
        print(f"이미지 로드 실패: {img_path}")
        return None, None

    h, w = img.shape[:2]

    # 1) resize
    scale = resize_limit / max(h, w)
    if scale < 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]

    # 2) grayscale + 선명화
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 75, 75)  # JPEG artifact 제거
    gray = cv2.equalizeHist(gray)                # 대비 증가
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)

    # 3) YOLO bbox 기반 중심 좌표 안정화
    x0 = w // 2
    y0 = h // 2
    R = int(min(h, w) * 0.45)

    # 4) edge 추출
    edges = cv2.Canny(blur, 40, 120)

    # 5) annulus mask 생성(더 강하게)
    yy, xx = np.indices(edges.shape)
    rr = np.sqrt((xx - x0) ** 2 + (yy - y0) ** 2)

    mask_ring = (rr > R * 0.22) & (rr < R * 0.88)
    mask_num_band = (rr > R * 0.55) & (rr < R * 0.72)

    # 숫자영역 제거
    edges[mask_num_band] = 0
    # 중심부 제거
    edges[rr < R * 0.22] = 0
    # 바깥 노이즈 제거
    edges[rr > R * 0.88] = 0

    # 6) angle voting
    thetas = np.deg2rad(np.arange(0, 360, 1.5))
    scores = []

    for th in thetas:
        xs = (x0 + np.cos(th) * np.linspace(R * 0.25, R * 0.88, 60)).astype(int)
        ys = (y0 - np.sin(th) * np.linspace(R * 0.25, R * 0.88, 60)).astype(int)

        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)

        scores.append(edges[ys, xs].sum())

    if len(scores) == 0 or max(scores) < 10:
        print("엣지 부족으로 탐지 실패")
        return None, None

    idx = int(np.argmax(scores))
    angle = (np.rad2deg(thetas[idx]) + 360) % 360

    # 7) 바늘 방향 보정(바늘은 항상 반대편도 강함)
    angle = (angle + 180) % 360

    # 8) 각도를 값으로 환산
    def cw_delta(a, b):
        return (a - b) % 360

    sweep = cw_delta(min_angle, max_angle)
    if sweep == 0:
        sweep = 360

    progressed = cw_delta(min_angle, angle)
    ratio = np.clip(progressed / sweep, 0, 1)
    value = min_value + ratio * (max_value - min_value)

    # 9) 시각화
    vis = img.copy()
    px = int(x0 + np.cos(np.deg2rad(angle)) * R * 0.85)
    py = int(y0 - np.sin(np.deg2rad(angle)) * R * 0.85)

    cv2.circle(vis, (x0, y0), 5, (0, 255, 0), -1)
    cv2.line(vis, (x0, y0), (px, py), (0, 0, 255), 3)
    cv2.putText(vis, f"{value:.2f}", (25, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 2)

    out_path = os.path.splitext(img_path)[0] + "_annulus_result.jpg"
    cv2.imwrite(out_path, vis)
    print("저장:", out_path)
    print(f"값={value:.2f}, 각도={angle:.2f}")

    return angle, value
    
# ---------------------------------
# 3) 이상 판단
# ---------------------------------
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


# ---------------------------------
# 4) YOLO + gauge 분석 (완전 통합)
# ---------------------------------
def analyze_module_gauges(image_path):
    model = YOLO("all.pt")
    results = model.predict(image_path, conf=0.5, device="cpu", verbose=False)

    img = cv2.imread(image_path)

    if len(results[0].boxes) == 0:
        print("❌ YOLO 탐지 결과 없음 (게이지 미검출)")
        return

    # -----------------------------
    # (A) full gauge box 찾기
    # -----------------------------
    gauge_boxes = []
    for b in results[0].boxes:
        cls = model.names[int(b.cls)]
        if cls in ["thermometer", "pressure_gauge"]:
            gauge_boxes.append(b)

    if not gauge_boxes:
        print("❌ thermometer / pressure_gauge 클래스 미검출")
        return

    # full crop 기준
    gx1, gy1, gx2, gy2 = map(int, gauge_boxes[0].xyxy[0])
    full_crop = img[gy1:gy2, gx1:gx2]

    # -----------------------------
    # (B) 중심은 full crop에서 1회만 검출
    # -----------------------------
    cx, cy, R = detect_gauge_center(full_crop)
    print(f"중심 검출 → cx={cx}, cy={cy}, R={R}")

    # -----------------------------
    # (C) 각 gauge ROI에 대해 angle 계산
    # -----------------------------
    for b in gauge_boxes:
        cls = model.names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])

        roi = img[y1:y2, x1:x2]

        # full crop 기준 → ROI 상대 좌표 보정
        rel_cx = cx + gx1 - x1
        rel_cy = cy + gy1 - y1

        cfg = THERMO_CFG if cls == "thermometer" else PRESS_CFG

        angle, value = detect_gauge_value_fast(
            roi, rel_cx, rel_cy, R, cfg
        )

        if angle is None:
            print(f"{cls}: 지침 검출 실패")
            continue

        msg, status = judge_abnormal(cls, value)
        print(f"{cls}: {value:.2f} → {msg}")


if __name__ == "__main__":
    analyze_module_gauges("KakaoTalk_20251119_203011424_03.jpg")
