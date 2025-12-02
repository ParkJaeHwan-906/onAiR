import cv2
import numpy as np
import sys
import os

def detect_center_hub(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)

    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=50,
        param1=80,
        param2=15,
        minRadius=5,
        maxRadius=35
    )

    h, w = img.shape[:2]
    cx = cy = None
    r = None

    if circles is not None:
        circles = np.uint16(np.around(circles))
        best = None
        best_dist = 1e9

        for c in circles[0, :]:
            x, y, rad = c
            dist = (x - w/2)**2 + (y - h/2)**2
            if dist < best_dist:
                best = c
                best_dist = dist

        cx, cy, r = best
        print(f"[INFO] 허브 검출됨 → center=({cx}, {cy}), radius={r}")

    else:
        print("[WARN] 허브(중앙 작은 원) 검출 실패 → 이미지 중심 사용")
        h, w = img.shape[:2]
        cx, cy = w//2, h//2

    return cx, cy, r


def detect_big_radius(img, cx, cy, r_small):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 1.2)
    edges = cv2.Canny(blur, 50, 150)

    h, w = gray.shape

    R_min = int(r_small * 12.0)
    R_max = int(r_small * 13.0)

    # 이미지 크기 넘어가는 것 방지
    R_max = min(R_max, int(min(h,w)*0.49))

    print(f"[DEBUG] big R 탐색 범위: {R_min} ~ {R_max}")

    thetas = np.deg2rad(np.arange(0,360,1))
    distances = []

    for th in thetas:
        for r in range(R_min, R_max):
            x = int(cx + np.cos(th)*r)
            y = int(cy - np.sin(th)*r)

            if x < 0 or x >= w or y < 0 or y >= h:
                break

            if edges[y, x] > 0:
                distances.append(r)
                break

    if len(distances) == 0:
        print("[ERROR] 큰 원 찾기 실패 (edge 부족)")
        return None

    R = int(np.median(distances))
    print(f"[INFO] 큰 원 R = {R}")
    return R






def visualize(img, cx, cy, r_small, R_big, out_path):
    vis = img.copy()

    # 중심점
    cv2.circle(vis, (cx, cy), 3, (0, 0, 255), -1)

    # 작은 원
    if r_small is not None:
        cv2.circle(vis, (cx, cy), r_small, (0, 255, 0), 2)

    # 큰 원
    if R_big is not None:
        cv2.circle(vis, (cx, cy), R_big, (255, 0, 0), 2)

    cv2.imwrite(out_path, vis)
    print("[INFO] 시각화 이미지 저장:", out_path)



# ======================================================
#  Main
# ======================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python detect_hub_center.py roi_debug/roi_167_42.png")
        sys.exit(0)

    img_path = sys.argv[1]
    img = cv2.imread(img_path)

    if img is None:
        print("이미지 로드 실패:", img_path)
        sys.exit(0)

    # 1) 허브 중심 + 작은 원 찾기
    cx, cy, r_small = detect_center_hub(img)

    # 2) 큰 원 반지름(R) 찾기
    R_big = detect_big_radius(img, cx, cy, r_small)

    # 3) 결과 시각화
    out_path = os.path.splitext(img_path)[0] + "_center_and_bigcircle.png"
    visualize(img, cx, cy, r_small, R_big, out_path)
