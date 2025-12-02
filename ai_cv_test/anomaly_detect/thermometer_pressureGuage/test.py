import cv2
import numpy as np
import os
from ultralytics import YOLO

# gauge config
THERMO_CFG = dict(min_angle=230, max_angle=330, min_val=0, max_val=100)
PRESS_CFG  = dict(min_angle=210, max_angle=330, min_val=0, max_val=2)



def detect_gauge_center(full_crop):
    gray = cv2.cvtColor(full_crop, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, 1, 200,
        param1=100, param2=22,
        minRadius=60, maxRadius=0
    )

    h, w = full_crop.shape[:2]

    if circles is None:
        return w//2, h//2, min(w, h)//2 - 40

    circles = np.uint16(np.around(circles))[0]
    c = max(circles, key=lambda c: c[2])
    return int(c[0]), int(c[1]), int(c[2])


# ----------------------------------------
# 2) 중심 고정 + ROI 기반 각도 계산 (이미지 기반)
# ----------------------------------------
def detect_gauge_value_fast(img, cx, cy, R, cfg):
    if img is None or img.size == 0:
        return None, None

    # 1) grayscale + JPEG artifact 제거
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 75, 75)
    gray = cv2.equalizeHist(gray)
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)

    # 2) edge
    edges = cv2.Canny(blur, 40, 120)

    h, w = img.shape[:2]
    yy, xx = np.indices(edges.shape)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

    # 3) annulus mask 강화
    mask_ring = (rr > R * 0.22) & (rr < R * 0.88)
    mask_num  = (rr > R * 0.55) & (rr < R * 0.72)

    edges[~mask_ring] = 0
    edges[mask_num] = 0

    # 4) angle voting
    thetas = np.deg2rad(np.arange(0, 360, 1.5))
    scores = []

    for th in thetas:
        xs = (cx + np.cos(th) * np.linspace(R*0.25, R*0.88, 60)).astype(int)
        ys = (cy - np.sin(th) * np.linspace(R*0.25, R*0.88, 60)).astype(int)

        xs = np.clip(xs, 0, w-1)
        ys = np.clip(ys, 0, h-1)

        scores.append(edges[ys, xs].sum())

    if max(scores) < 10:
        return None, None

    idx = int(np.argmax(scores))
    angle = (np.rad2deg(thetas[idx]) + 360) % 360
    angle = (angle + 180) % 360  # 반대편 보정

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

    # 6) 각도 → 값
    def cw(a, b): return (a - b) % 360

    sweep = cw(cfg["min_angle"], cfg["max_angle"])
    sweep = 360 if sweep == 0 else sweep

    prog = cw(cfg["min_angle"], angle)
    ratio = float(np.clip(prog / sweep, 0, 1))
    value = cfg["min_val"] + ratio * (cfg["max_val"] - cfg["min_val"])

    return angle, value


# ---------------------------------
# 3) YOLO + full crop 중심 → ROI 상대좌표로 angle 계산
# ---------------------------------
def analyze_module_gauges(image_path):
    model = YOLO("all.pt")
    results = model.predict(image_path, conf=0.5, device="cpu", verbose=False)

    img = cv2.imread(image_path)
    if img is None:
        print("이미지 로드 실패:", image_path)
        return

    # 게이지 박스 목록
    gauges = []
    for box in results[0].boxes:
        cls = model.names[int(box.cls)]
        if cls in ["thermometer", "pressure_gauge"]:
            gauges.append((cls, box))

    if not gauges:
        print("❌ 게이지 미검출")
        return

    # full gauge crop은 첫 번째 박스로 사용
    first_cls, first_box = gauges[0]
    gx1, gy1, gx2, gy2 = map(int, first_box.xyxy[0])
    full_crop = img[gy1:gy2, gx1:gx2]

    # full crop 기준 중심/반경 1회 검출
    cx, cy, R = detect_gauge_center(full_crop)
    print(f"중심={cx}, {cy}, R={R}")

    # 모든 게이지 ROI 분석
    for cls, box in gauges:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        roi = img[y1:y2, x1:x2]

        # ROI 내 상대 중심 계산
        rel_cx = cx + gx1 - x1
        rel_cy = cy + gy1 - y1

        cfg = THERMO_CFG if cls == "thermometer" else PRESS_CFG

        angle, value = detect_gauge_value_fast(roi, rel_cx, rel_cy, R, cfg)

        if angle is None:
            print(f"{cls}: 지침 검출 실패")
            continue

        print(f"{cls}: angle={angle:.2f}, value={value:.2f}")


if __name__ == "__main__":
    analyze_module_gauges("ther.png")
    analyze_module_gauges("ther2.png")
