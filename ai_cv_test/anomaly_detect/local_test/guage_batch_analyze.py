import os
import glob
import cv2
import numpy as np
from ultralytics import YOLO

# -----------------------------
# 설정
# -----------------------------
MODEL_PATH = "models/final_v2.pt"  # YOLO 모델 경로

THERMO_CFG = dict(min_angle=230, max_angle=330, min_val=0,   max_val=100)
PRESS_CFG  = dict(min_angle=210, max_angle=330, min_val=0.0, max_val=1.0)

ALLOWED_CLASSES = ["pressure_gauge", "thermometer", "gauge"]


# -----------------------------
# 공통 유틸
# -----------------------------
def cw_delta(a, b):
    return (a - b) % 360


def angle_to_value(angle_deg, cfg):
    min_angle = cfg["min_angle"]
    max_angle = cfg["max_angle"]
    min_val   = cfg["min_val"]
    max_val   = cfg["max_val"]

    sweep = cw_delta(min_angle, max_angle)
    if sweep == 0:
        sweep = 360

    progressed = cw_delta(min_angle, angle_deg)
    ratio = np.clip(progressed / sweep, 0, 1)
    value = min_val + ratio * (max_val - min_val)
    return float(value)


# -----------------------------
# 1) YOLO 기반 ROI 추출
# -----------------------------
def detect_and_crop_gauges(img, img_name, model, conf_thres=0.5, roi_dir="roi_debug"):
    os.makedirs(roi_dir, exist_ok=True)
    results = model(img)[0]
    rois = []

    idx = 0
    for box in results.boxes:
        cls_idx = int(box.cls)
        cls_name = results.names[cls_idx]

        if cls_name not in ALLOWED_CLASSES:
            continue

        if float(box.conf) < conf_thres:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        crop = img[y1:y2, x1:x2]
        roi_fname = f"{os.path.splitext(img_name)[0]}_{cls_name}_{idx}.png"
        roi_path = os.path.join(roi_dir, roi_fname)
        cv2.imwrite(roi_path, crop)

        rois.append((cls_name, crop, roi_fname))
        idx += 1

    return rois


# -----------------------------
# 2) 허브 중심 탐지
# -----------------------------
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
            dist = (x - cx_img)**2 + (y - cy_img)**2

            # 10% 허용 범위 이내인지 체크
            dx = abs(x - cx_img)
            dy = abs(y - cy_img)

            if dx < w * 0.15 and dy < h * 0.15:   # ★ 여기만 10%로 변경
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
    blur = cv2.GaussianBlur(gray, (5,5), 1.2)

    h, w = gray.shape

    # 1) 최저 1% 픽셀(어두운 영역) 찾기
    thresh_val = np.percentile(blur, 3)  # 하위 1% 픽셀값
    mask = (blur <= thresh_val).astype(np.uint8) * 255

    if debug_dir:
        cv2.imwrite(f"{debug_dir}/hub_dark_mask.png", mask)

    # 2) 연결된 어두운 블롭 탐지
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)

    if num_labels <= 1:
        # 허브가 너무 약해서 안 보이면 이미지 중앙 fallback
        cx, cy = w//2, h//2
        print("[WARN] intensity hub not found → fallback to center")
        return cx, cy, None

    # 3) 가장 '해상도 높은 blob' 찾기
    best_idx = None
    best_score = -1

    for i in range(1, num_labels):  # 0은 배경
        area = stats[i, cv2.CC_STAT_AREA]

        if area < 5 or area > 500:  # 허브 크기 제한
            continue

        # blob의 중심
        cx_blob, cy_blob = centroids[i]
        # ROI 중심과 가까울수록 점수 상승
        dist_center = (cx_blob - w/2)**2 + (cy_blob - h/2)**2
        score = -dist_center  # 중심과 가까울수록 good

        if score > best_score:
            best_score = score
            best_idx = i

    if best_idx is None:
        cx, cy = w//2, h//2
        print("[WARN] hub not found (no blob) → fallback center")
        return cx, cy, None

    cx_hub, cy_hub = centroids[best_idx]
    cx_hub, cy_hub = int(cx_hub), int(cy_hub)

    # 4) 허브 radius 대략 구하기 (blob의 평균 반경)
    ys, xs = np.where(labels == best_idx)
    dists = np.sqrt((xs - cx_hub)**2 + (ys - cy_hub)**2)
    r_small = int(np.mean(dists))

    if debug_dir:
        vis = img.copy()
        cv2.circle(vis, (cx_hub, cy_hub), 3, (0,0,255), -1)
        cv2.circle(vis, (cx_hub, cy_hub), r_small, (0,255,0), 2)
        cv2.imwrite(f"{debug_dir}/hub_intensity_detected.png", vis)

    print(f"[INFO] intensity hub detected → ({cx_hub},{cy_hub}), r={r_small}")

    return cx_hub, cy_hub, r_small



# -----------------------------
# 3) 큰 원 반지름 탐지
# -----------------------------
def detect_big_radius(img, cx, cy, r_small):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)
    edges = cv2.Canny(blur, 80, 200)

    h, w = gray.shape

    if r_small is not None:
        R_min = int(r_small * 11.0)
        R_max = int(r_small * 14.0)
    else:
        R_min = int(min(h, w) * 0.35)
        R_max = int(min(h, w) * 0.48)

    R_max = min(R_max, int(min(h, w) * 0.49))

    print(f"[DEBUG] search R range: {R_min} ~ {R_max}")

    thetas = np.deg2rad(np.arange(0, 360, 1))
    distances = []

    for th in thetas:
        for r in range(R_min, R_max):
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


# -----------------------------
# 5) 시각화
# -----------------------------
def draw_angle_line(img, center, angle_deg, R, color=(0, 0, 255)):
    out = img.copy()
    x0, y0 = center
    theta = np.deg2rad(angle_deg)

    x1 = int(x0 + np.cos(theta) * R)
    y1 = int(y0 - np.sin(theta) * R)

    cv2.circle(out, (x0, y0), 3, (0, 255, 0), -1)
    cv2.line(out, (x0, y0), (x1, y1), color, 3)
    return out


# -----------------------------
# 6) ROI 단위 게이지 분석
# -----------------------------
def analyze_gauge_roi(roi, cls_name, out_prefix, result_dir="results", debug_dir="debug"):
    import matplotlib.pyplot as plt
    os.makedirs(result_dir, exist_ok=True)
    dbg = os.path.join(debug_dir, out_prefix)
    os.makedirs(dbg, exist_ok=True)

    # -----------------------------
    # 0) ROI 저장
    # -----------------------------
    cv2.imwrite(f"{dbg}/01_roi.png", roi)

    # -----------------------------
    # 1) 중심 허브 탐지
    # -----------------------------
    cx, cy, r_small = detect_center_hub_intensity(roi)

    hub_vis = roi.copy()
    cv2.circle(hub_vis, (cx, cy), 3, (0, 255, 0), -1)
    if r_small is not None:
        cv2.circle(hub_vis, (cx, cy), r_small, (255, 255, 0), 2)
    cv2.imwrite(f"{dbg}/05_center_hub.png", hub_vis)

    # -----------------------------
    # 2) 큰 원 반지름
    # -----------------------------
    R = detect_big_radius(roi, cx, cy, r_small)

    big_vis = hub_vis.copy()
    cv2.circle(big_vis, (cx, cy), R, (255, 0, 0), 2)
    cv2.imwrite(f"{dbg}/06_big_circle.png", big_vis)

    if R is None:
        print("[WARN] big circle fail, skip")
        return

    # -----------------------------
    # 3) Dark-only Angle Voting
    # -----------------------------
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(f"{dbg}/02_gray.png", gray)

    blur = cv2.GaussianBlur(gray, (5,5), 1.2)
    cv2.imwrite(f"{dbg}/03_blur.png", blur)

    edges = cv2.Canny(blur, 40, 120)
    cv2.imwrite(f"{dbg}/04_edges.png", edges)

    best_angle, scores = dark_only_angle_voting(gray, (cx,cy), R)

    # -----------------------------
    # 3-1) score heatmap 저장
    # -----------------------------
    plt.figure(figsize=(10,4))
    plt.plot(scores)
    plt.title("Angle Score Heatmap")
    plt.xlabel("Angle (deg)")
    plt.ylabel("Score")
    plt.axvline(best_angle, color='r', linestyle='--')
    plt.savefig(f"{dbg}/07_angle_voting_heatmap.png")
    plt.close()

    # -----------------------------
    # 4) 값 계산
    # -----------------------------
    cfg = THERMO_CFG if ("thermo" in cls_name) else PRESS_CFG
    value = angle_to_value(best_angle, cfg)

    # -----------------------------
    # 5) 최종 라인 + 텍스트
    # -----------------------------
    final = draw_angle_line(roi, (cx,cy), best_angle, R)

    text = f"Angle: {best_angle} deg   Value: {value:.2f}"
    h, w = roi.shape[:2]
    font_scale = max(0.4, min(1.2, h / 800))

    if value >= 40:
        status = "HIGH TEMP"
        color = (0, 0, 255)    # 빨강
    else:
        status = "NORMAL"
        color = (0, 200, 0)    # 초록


    text2 = f"Status: {status}"

    
    cv2.putText(final, text, (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (255, 0, 180), 2, cv2.LINE_AA)
    
    cv2.putText(final, text2, (20, h-20),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                color, 2)
    cv2.imwrite(f"{dbg}/08_final_angle_line.png", final)

    # 결과도 별도 저장
    out_img_path = os.path.join(result_dir, f"{out_prefix}_angle.png")
    cv2.imwrite(out_img_path, final)

    print(f"[RESULT] {out_prefix} | {cls_name} | angle={best_angle}, value={value:.2f}")
    print(f"Saved: {out_img_path}")



# -----------------------------
# 7) 폴더 단위 전체 처리
# -----------------------------
def process_folder(image_dir,
                   roi_dir="roi_debug",
                   result_dir="results",
                   conf_thres=0.5):
    model = YOLO(MODEL_PATH)

    img_paths = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        img_paths.extend(glob.glob(os.path.join(image_dir, ext)))

    img_paths = sorted(img_paths)

    if not img_paths:
        print("no images found in", image_dir)
        return

    print(f"[INFO] found {len(img_paths)} images")

    for img_path in img_paths:
        img_name = os.path.basename(img_path)
        print("\n==============================")
        print(f"[INFO] processing {img_name}")
        img = cv2.imread(img_path)

        if img is None:
            print("[ERROR] image load failed:", img_path)
            continue

        rois = detect_and_crop_gauges(img, img_name, model,
                                      conf_thres=conf_thres,
                                      roi_dir=roi_dir)

        if not rois:
            print("[WARN] no gauge detected in", img_name)
            continue

        for idx, (cls_name, roi, roi_fname) in enumerate(rois):
            prefix = os.path.splitext(roi_fname)[0]
            analyze_gauge_roi(roi, cls_name, prefix, result_dir=result_dir)


# -----------------------------
# Entry
# -----------------------------
if __name__ == "__main__":
    # 여기 경로만 네가 쓰는 이미지 폴더로 바꾸면 됨
    IMAGE_DIR = "./test"      # 원본 이미지 폴더
    ROI_DIR   = "./debug"   # 잘린 ROI 저장 폴더
    RESULT_DIR = "./test_result"    # 각도 라인 그린 결과 저장 폴더

    process_folder(IMAGE_DIR, roi_dir=ROI_DIR, result_dir=RESULT_DIR, conf_thres=0.5)
