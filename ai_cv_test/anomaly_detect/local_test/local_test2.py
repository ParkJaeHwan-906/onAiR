import os
import glob
import cv2
import numpy as np
from ultralytics import YOLO

MODEL_PATH = "models/final_v2.pt"

THERMO_CFG = dict(min_angle=225, max_angle=315, min_val=0,   max_val=100)
PRESS_CFG  = dict(min_angle=230, max_angle=325, min_val=0.0, max_val=1.5)

ALLOWED_CLASSES = ["pressure_gauge", "thermometer", "gauge"]

def cw_delta(a, b):
    return (a - b) % 360

def angle_to_value(angle_deg, cfg):
    min_angle = cfg["min_angle"]
    max_angle = cfg["max_angle"]
    min_val   = cfg["min_val"]
    max_val   = cfg["max_val"]

    sweep = cw_delta(min_angle, max_angle)
    progressed = cw_delta(min_angle, angle_deg)
    ratio = np.clip(progressed / sweep, 0, 1)
    return float(min_val + ratio * (max_val - min_val))


# ==============================
# 1) YOLO ROI
# ==============================
def detect_and_crop_gauges(img, img_name, model, th=0.5, roi_dir="roi_debug"):
    os.makedirs(roi_dir, exist_ok=True)
    results = model(img)[0]
    rois = []
    idx = 0

    for box in results.boxes:
        cls = results.names[int(box.cls)]
        if cls not in ALLOWED_CLASSES: continue
        if float(box.conf) < th: continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        crop = img[y1:y2, x1:x2]
        fname = f"{os.path.splitext(img_name)[0]}_{cls}_{idx}.png"
        cv2.imwrite(os.path.join(roi_dir, fname), crop)
        rois.append((cls, crop, fname))
        idx += 1

    return rois


# ==============================
# 2) 중심 탐지 (개선)
# ==============================
def detect_center_hub_new(roi):
    h, w = roi.shape[:2]
    cx0, cy0 = w//2, h//2

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    L = int(min(w, h) * 0.10)
    y1, y2 = cy0 - L, cy0 + L
    x1, x2 = cx0 - L, cx0 + L
    y1, x1 = max(y1,0), max(x1,0)
    y2, x2 = min(y2,h-1), min(x2,w-1)
    local = gray[y1:y2, x1:x2]

    edges = cv2.Canny(local, 50, 150)
    ys, xs = np.where(edges > 0)
    if len(xs) > 3:
        cx = int(np.mean(xs)) + x1
        cy = int(np.mean(ys)) + y1
        return cx, cy

    blur = cv2.GaussianBlur(gray, (3,3), 1)
    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT,
        dp=1.3, minDist=25,
        param1=80, param2=12,
        minRadius=4, maxRadius=12
    )
    if circles is not None:
        c = np.uint16(np.around(circles[0]))[0]
        return int(c[0]), int(c[1])

    Z = int(np.percentile(gray, 5))
    mask = (gray < Z).astype(np.uint8)
    ys, xs = np.where(mask > 0)
    if len(xs) > 5:
        cx = int(np.median(xs))
        cy = int(np.median(ys))
        return cx, cy

    return cx0, cy0


# ==============================
# 3) 큰 원 반지름
# ==============================
def detect_big_radius(roi, cx, cy):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    h, w = gray.shape

    Rmin = int(min(h,w)*0.38)
    Rmax = int(min(h,w)*0.49)

    thetas = np.deg2rad(np.arange(0, 360, 2))
    ds = []
    for th in thetas:
        for r in range(Rmin, Rmax):
            x = int(cx + np.cos(th)*r)
            y = int(cy - np.sin(th)*r)
            if x<0 or x>=w or y<0 or y>=h: break
            if edges[y, x]>0:
                ds.append(r)
                break

    if not ds: return None
    return int(np.median(ds))


# ==============================
# 4) Angle
# ==============================
def dark_angle(gray, center, R):
    x0,y0 = center
    h,w = gray.shape
    scores = []
    for ang in range(360):
        th = np.deg2rad(ang)
        rs = np.arange(0,R,1)
        xs = (x0 + np.cos(th)*rs).astype(int)
        ys = (y0 - np.sin(th)*rs).astype(int)
        v = (xs>=0)&(xs<w)&(ys>=0)&(ys<h)
        xs, ys = xs[v], ys[v]
        scores.append(np.sum(gray[ys,xs] < 130))
    scores = np.array(scores)
    return int(np.argmax(scores))


# ==============================
# 5) ROI 분석
# ==============================
def analyze(roi, cls, prefix, result_dir="results"):
    os.makedirs(result_dir, exist_ok=True)

    roi = cv2.resize(roi, (300,300))    # 표준화
    cx, cy = detect_center_hub_new(roi)
    R = detect_big_radius(roi, cx, cy)
    if R is None: return

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    ang = dark_angle(gray, (cx,cy), R)

    cfg = THERMO_CFG if ("thermo" in cls) else PRESS_CFG
    val = angle_to_value(ang, cfg)

    out = roi.copy()
    th = np.deg2rad(ang)
    x1,y1 = int(cx + np.cos(th)*R), int(cy - np.sin(th)*R)
    cv2.circle(out,(cx,cy),3,(0,255,0),-1)
    cv2.line(out,(cx,cy),(x1,y1),(0,0,255),3)

    # ------------------------------------------
    # 게이지 min/max angle 도 시각화
    # ------------------------------------------
    start_ang = cfg["min_angle"]
    end_ang   = cfg["max_angle"]

    # 시작 각도
    th_s = np.deg2rad(start_ang)
    xs = int(cx + np.cos(th_s)*R)
    ys = int(cy - np.sin(th_s)*R)
    cv2.line(out, (cx,cy), (xs,ys), (0,255,255), 2)   # 노란색

    # 끝 각도
    th_e = np.deg2rad(end_ang)
    xe = int(cx + np.cos(th_e)*R)
    ye = int(cy - np.sin(th_e)*R)
    cv2.line(out, (cx,cy), (xe,ye), (255,255,0), 2)   # 하늘색


    txt = f"{ang}deg / {val:.2f}"
    cv2.putText(out, txt, (10,40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (255,0,180),2)

    cv2.imwrite(os.path.join(result_dir, f"{prefix}.png"), out)
    print(f"[DONE] {prefix} | {cls} | angle={ang}, value={val:.2f}")


# ==============================
# Entry
# ==============================
def process_folder(image_dir, roi_dir="roi_debug", result_dir="results"):
    model = YOLO(MODEL_PATH)
    img_paths = sorted(glob.glob(os.path.join(image_dir, "*.*")))

    print(f"[INFO] {len(img_paths)} images")
    for path in img_paths:
        name = os.path.basename(path)
        print(f"\n[PROC] {name}")
        img = cv2.imread(path)
        if img is None: continue

        rois = detect_and_crop_gauges(img, name, model, roi_dir=roi_dir)
        for (cls, roi, fname) in rois:
            prefix = os.path.splitext(fname)[0]
            analyze(roi, cls, prefix, result_dir=result_dir)


if __name__ == "__main__":
    process_folder("./test", roi_dir="./debug", result_dir="./test_result")
