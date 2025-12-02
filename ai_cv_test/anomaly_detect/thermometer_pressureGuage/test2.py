import cv2
import numpy as np
import os
from ultralytics import YOLO


# ============================================================
#  게이지 설정
# ============================================================
THERMO_CFG = dict(min_angle=220, max_angle=320, min_val=0, max_val=100)
PRESS_CFG  = dict(min_angle=210, max_angle=330, min_val=0, max_val=1.5)


# ============================================================
# 1) JPEG-friendly 전처리 + Edge 강화
# ============================================================
def preprocess_for_gauge(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 노이즈 제거 + JPEG 아티팩트 완화
    gray = cv2.medianBlur(gray, 5)
    gray = cv2.bilateralFilter(gray, 9, 110, 110)

    # 대비 증가
    gray = cv2.equalizeHist(gray)

    # 샤프닝
    sharp = cv2.addWeighted(
        gray, 1.6,
        cv2.GaussianBlur(gray, (0, 0), 2),
        -0.6, 0
    )
    return sharp


# ============================================================
# 2) Sobel 기반 중심 검출 (Hough 실패 대비)
# ============================================================
def detect_center_sobel(img):
    sobel = cv2.Sobel(img, cv2.CV_16U, 1, 1, ksize=5)
    M = cv2.moments(sobel)

    h, w = img.shape[:2]
    cx = int(M["m10"] / (M["m00"] + 1e-6))
    cy = int(M["m01"] / (M["m00"] + 1e-6))

    # 너무 치우치면 안전하게 가운데로 보정
    if cx < w * 0.2 or cx > w * 0.8:
        cx = w // 2
    if cy < h * 0.2 or cy > h * 0.8:
        cy = h // 2

    return cx, cy


# ============================================================
# 3) JPEG-friendly 게이지 바늘 값 계산
#    (현재 구조 유지 + 방향 판별만 강화)
# ============================================================
def detect_gauge_value_fast(img, cfg):
    min_angle = cfg["min_angle"]
    max_angle = cfg["max_angle"]
    min_value = cfg["min_val"]
    max_value = cfg["max_val"]

    sharp = preprocess_for_gauge(img)
    h, w = sharp.shape[:2]

    cx, cy = detect_center_sobel(sharp)
    R = int(min(h, w) * 0.47)

    edges = cv2.Canny(sharp, 25, 90)

    yy, xx = np.indices(edges.shape)
    rr = np.sqrt((xx - cx)**2 + (yy - cy)**2)

    # ----- 1) 바늘 구간 / 숫자 구간 분리 -----
    pointer_band = (rr > R * 0.18) & (rr < R * 0.60)   # 바늘 몸통
    outer_band   = (rr > R * 0.60) & (rr < R * 0.90)   # 숫자/눈금

    edges_ptr  = edges.copy()
    edges_ptr[~pointer_band] = 0

    edges_outer = edges.copy()
    edges_outer[~outer_band] = 0

    # 엣지가 너무 적으면 기존처럼 전체 사용
    if edges_ptr.sum() < 500:
        edges_ptr = edges
        edges_outer = np.zeros_like(edges)

    # ----- 2) 각도별 스코어 계산 -----
    thetas = np.deg2rad(np.arange(0, 360, 1.5))
    scores_inner = []
    scores_outer = []

    for th in thetas:
        xs = (cx + np.cos(th) * np.linspace(R*0.25, R*0.9, 50)).astype(int)
        ys = (cy - np.sin(th) * np.linspace(R*0.25, R*0.9, 50)).astype(int)
        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)

        scores_inner.append(edges_ptr[ys, xs].sum())
        scores_outer.append(edges_outer[ys, xs].sum())

    scores_inner = np.asarray(scores_inner, dtype=np.float32)
    scores_outer = np.asarray(scores_outer, dtype=np.float32)

    # ----- 3) 게이지 유효 각도 범위 밖은 버리기 -----
    degs = (np.rad2deg(thetas) + 180) % 360  # 기존과 동일한 기준
    def cw(a, b): return (a - b) % 360
    sweep = cw(min_angle, max_angle)
    if sweep == 0:
        sweep = 360
    margin = 15.0  # 여유 각도

    valid_mask = []
    for d in degs:
        prog = cw(min_angle, d)
        valid_mask.append(prog <= (sweep + margin))
    valid_mask = np.array(valid_mask, dtype=bool)

    # 유효 범위 밖은 스코어 0
    scores_inner[~valid_mask] = 0
    scores_outer[~valid_mask] = 0

    # ----- 4) 최종 스코어: 중심 쪽을 두 배로 가중 -----
    scores = scores_inner * 2.0 + scores_outer * 0.3

    if scores.max() < 10:
        return None, None, None

    best = int(np.argmax(scores))
    angle = (degs[best]) % 360

    # 5) 양쪽 비교(needle 방향 결정)
    def score_dir(a):
        xs = (cx + np.cos(np.deg2rad(a)) * np.linspace(R*0.3, R*0.9, 30)).astype(int)
        ys = (cy - np.sin(np.deg2rad(a)) * np.linspace(R*0.3, R*0.9, 30)).astype(int)
        xs = np.clip(xs, 0, w-1)
        ys = np.clip(ys, 0, h-1)
        return edges[ys, xs].sum()

    opp = (angle + 180) % 360
    if score_dir(opp) > score_dir(angle) * 1.15:
        angle = opp
        
    # ----- 5) 값 환산 -----
    prog = cw(min_angle, angle)
    ratio = np.clip(prog / sweep, 0, 1)
    value = min_value + ratio * (max_value - min_value)

    px = int(cx + np.cos(np.deg2rad(angle)) * R * 0.85)
    py = int(cy - np.sin(np.deg2rad(angle)) * R * 0.85)

    return angle, value, (cx, cy, px, py, R)

# ============================================================
# 4) 이상 판단
# ============================================================
def judge_abnormal(sensor_type, value):
    if sensor_type == "thermometer":
        if value > 80:
            return "온도 과열", "high"
        if value < 5:
            return "온도 너무 낮음", "low"
        return "정상", "normal"

    if sensor_type == "pressure_gauge":
        if value > 1.5:
            return "압력 과다", "high"
        if value < 0.2:
            return "압력 부족", "low"
        return "정상", "normal"

    return "Unknown", "unknown"


# ============================================================
# 5) YOLO + 전체 처리
# ============================================================
def analyze_module_gauges(image_path):
    model = YOLO("all2.pt")
    results = model.predict(image_path, conf=0.45, device="cpu", verbose=False)

    img = cv2.imread(image_path)
    if img is None:
        print("이미지 로드 실패")
        return

    print("YOLO box detected:", len(results[0].boxes))

    gauge_boxes = []
    for b in results[0].boxes:
        cls = model.names[int(b.cls)]
        if cls in ["thermometer", "pressure_gauge"]:
            gauge_boxes.append(b)

    if not gauge_boxes:
        print("❌ thermometer / pressure_gauge 미검출")
        return

    for b in gauge_boxes:
        cls = model.names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])

        roi = img[y1:y2, x1:x2]
        cfg = THERMO_CFG if cls == "thermometer" else PRESS_CFG

        angle, value, visinfo = detect_gauge_value_fast(roi, cfg)

        if angle is None:
            print(f"{cls}: 바늘 검출 실패")
            continue

        print(f"{cls}: value={value:.2f}  angle={angle:.2f}")

        cx, cy, px, py, R = visinfo

        vis = roi.copy()
        cv2.circle(vis, (cx, cy), 6, (0, 255, 0), -1)
        cv2.line(vis, (cx, cy), (px, py), (0, 0, 255), 3)
        cv2.putText(vis, f"{value:.2f}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (0, 255, 255), 2)

        out_path = "result3/"+os.path.splitext(image_path)[0] + f"_{cls}_result.jpg"
        cv2.imwrite(out_path, vis)
        print("시각화 저장 →", out_path)


# ============================================================
# 실행
# ============================================================
if __name__ == "__main__":
    # analyze_module_gauges("10.jpg")
    # analyze_module_gauges("11.jpg")
    # analyze_module_gauges("3.jpg")
    # # analyze_module_gauges("ther4.jpeg")
    # # analyze_module_gauges("pres.jpeg")
    # # analyze_module_gauges("pres2.jpeg")
    # analyze_module_gauges("both.jpeg")
    analyze_module_gauges("7.jpg")
    # analyze_module_gauges("5.jpg")
    # analyze_module_gauges("6.jpg")
    # analyze_module_gauges("7.jpg")
    # analyze_module_gauges("new3.jpg")
    # analyze_module_gauges("new4.jpg")