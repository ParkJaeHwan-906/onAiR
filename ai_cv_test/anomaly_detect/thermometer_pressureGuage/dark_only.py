import cv2
import numpy as np
import math
import os

THERMO_CFG = dict(min_angle=230, max_angle=330, min_val=0, max_val=100)
PRESS_CFG  = dict(min_angle=210, max_angle=330, min_val=0, max_val=2)

# ----------------------------------------
# 1) 중앙 허브(Hub) 탐지 (Hough + fallback)
# ----------------------------------------
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

    if circles is not None:
        circles = np.uint16(np.around(circles))
        best = None
        best_dist = 1e9

        for c in circles[0]:
            x, y, r = c
            dist = (x - w/2)**2 + (y - h/2)**2
            if dist < best_dist:
                best = c
                best_dist = dist

        cx, cy, r_small = best
        print(f"[INFO] Hub detected → ({cx},{cy}), r={r_small}")
        return cx, cy, r_small

    cx, cy = w//2, h//2
    print("[WARN] Hub not found. Using image center.")
    return cx, cy, None


# ----------------------------------------
# 2) 큰 원 반지름 R 추정 (Radial Edge)
# ----------------------------------------
def detect_big_radius(img, cx, cy, r_small):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 1.2)
    edges = cv2.Canny(blur, 40, 120)

    h, w = gray.shape

    # 작은 원의 11~14배 범위만 스캔 (실험으로 보정됨)
    R_min = int(r_small * 11)
    R_max = int(r_small * 14)

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

    if len(distances) == 0:
        print("[ERROR] Big circle detection failed")
        return None

    R = int(np.median(distances))
    print(f"[INFO] Big radius R = {R}")
    return R


# ----------------------------------------
# 3) Dark-only Angle Voting (가장 정확)
# ----------------------------------------
def dark_only_angle_voting(gray_img, center, R, dark_thresh=120):
    h, w = gray_img.shape
    x0, y0 = center

    scores = []

    for ang in range(360):
        theta = np.deg2rad(ang)

        xs = (x0 + np.cos(theta) * np.arange(0, R)).astype(int)
        ys = (y0 - np.sin(theta) * np.arange(0, R)).astype(int)

        valid = (xs>=0)&(xs<w)&(ys>=0)&(ys<h)
        xs, ys = xs[valid], ys[valid]

        if len(xs) == 0:
            scores.append(0)
            continue

        dark_score = np.sum(gray_img[ys, xs] < dark_thresh)
        scores.append(dark_score)

    best_angle = int(np.argmax(scores))
    print(f"[INFO] Best angle = {best_angle}°")

    return best_angle, np.array(scores)


# ----------------------------------------
# 4) 시각화 라인 그리기
# ----------------------------------------
def draw_angle_line(img, center, angle_deg, R, color=(0,0,255)):
    out = img.copy()
    x0, y0 = center
    theta = np.deg2rad(angle_deg)

    x1 = int(x0 + np.cos(theta) * R)
    y1 = int(y0 - np.sin(theta) * R)

    cv2.line(out, (x0,y0), (x1,y1), color, 3)
    return out


# ----------------------------------------
# 5) 값 환산 (0~100 thermometer)
# ----------------------------------------
def angle_to_value(angle_deg, cfg):
    min_angle = cfg["min_angle"]
    max_angle = cfg["max_angle"]
    min_val   = cfg["min_val"]
    max_val   = cfg["max_val"]

    # 시계방향 기준 각도 차이
    def cw_delta(a, b):
        return (a - b) % 360

    # 전체 스윕(측정 범위)
    sweep = cw_delta(min_angle, max_angle)
    if sweep == 0:
        sweep = 360  # 예외 처리

    # min_angle에서 현재 angle_deg까지 진행된 양
    progressed = cw_delta(min_angle, angle_deg)

    # 0~1 비율
    ratio = np.clip(progressed / sweep, 0, 1)

    # 실제 값으로 매핑
    value = min_val + ratio * (max_val - min_val)
    return value

# ----------------------------------------
# Main Pipeline
# ----------------------------------------
def analyze_gauge(img_path, out_path="final_result.png"):

    src = cv2.imread(img_path)
    if src is None:
        print("Image load fail")
        return

    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)

    # 1) 중심 허브
    cx, cy, r_small = detect_center_hub(src)

    # 2) 큰 원 반지름
    R = detect_big_radius(src, cx, cy, r_small)

    # 3) Dark-only voting
    best_angle, _ = dark_only_angle_voting(gray, (cx,cy), R)

    # 4) 시각화
    out = draw_angle_line(src, (cx,cy), best_angle, R)
    cv2.imwrite(out_path, out)

    # 5) 값 계산
    cfg = THERMO_CFG  # or PRESS_CFG
    value = angle_to_value(best_angle, cfg)
    print(f"[RESULT] Final Value = {value:.2f}")

    print("Saved:", out_path)
    return best_angle, value


# 실행
if __name__ == "__main__":
    analyze_gauge("roi_debug/roi_192_908.png", "final_pres1.png")



