import cv2
import numpy as np

def angle_voting(roi, cx, cy, R):
    """
    roi  : ROI 이미지 (numpy array)
    cx, cy : ROI 내부 기준 중심
    R : 게이지의 큰 반지름
    """
    h, w = roi.shape[:2]

    # -------------------------------
    # 1) Edge + 전처리
    # -------------------------------
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 75, 75)   # 노이즈 억제 + 엣지 보존
    gray = cv2.equalizeHist(gray)                 # 대비 증가
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)
    edges = cv2.Canny(blur, 40, 120)

    # -------------------------------
    # 2) 마스크링 (중심/숫자/바깥쪽 제거)
    # -------------------------------
    yy, xx = np.indices((h, w))
    rr = np.sqrt((xx - cx)**2 + (yy - cy)**2)

    mask_center = rr < R * 0.15
    mask_outer = rr > R * 0.90

    edges[mask_center] = 0
    edges[mask_outer] = 0

    # -------------------------------
    # 3) Angle Voting
    # -------------------------------
    thetas = np.deg2rad(np.arange(0, 360, 1.5))
    scores = []

    for th in thetas:
        rs = np.linspace(R * 0.25, R * 0.88, 60)
        xs = (cx + np.cos(th) * rs).astype(int)
        ys = (cy - np.sin(th) * rs).astype(int)

        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)

        scores.append(edges[ys, xs].sum())

    # -------------------------------
    # 4) 가장 높은 점수 → 바늘 방향
    # -------------------------------
    if max(scores) < 10:
        print("❌ 엣지 부족 → 바늘 검출 실패")
        return None, None, edges

    idx = int(np.argmax(scores))
    angle = (np.rad2deg(thetas[idx]) + 360) % 360

    # -------------------------------
    # 5) 반대 방향 검사 (바늘 반전 보정)
    # -------------------------------
    opp = (angle + 180) % 360

    def score_dir(deg):
        rs = np.linspace(R * 0.25, R * 0.88, 40)
        xs = (cx + np.cos(np.deg2rad(deg)) * rs).astype(int)
        ys = (cy - np.sin(np.deg2rad(deg)) * rs).astype(int)
        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)
        return edges[ys, xs].sum()

    if score_dir(opp) > score_dir(angle) * 1.15:
        angle = opp

    return angle, scores[idx], edges

def draw_angle_line(roi, cx, cy, angle_deg, R, color=(0, 0, 255)):
    """
    roi        : ROI 이미지
    cx, cy     : 중심 좌표
    angle_deg  : 검출된 각도 (0~360)
    R          : 큰 원 반지름
    color      : 시각화 선 색 (기본 빨강)

    반환값 : 시각화된 이미지
    """
    vis = roi.copy()

    rad = np.deg2rad(angle_deg)

    x_end = int(cx + np.cos(rad) * R)
    y_end = int(cy - np.sin(rad) * R)

    # 중심점
    cv2.circle(vis, (cx, cy), 5, (0, 255, 0), -1)

    # 방향(Line)
    cv2.line(vis, (cx, cy), (x_end, y_end), color, 3)

    return vis
    

if __name__ == "__main__":
    roi = cv2.imread("roi_debug/roi_167_42.png")
    angle, score, edge_img = angle_voting(roi, 285, 247, 177)
    print("바늘 각도 =", angle)
    
    vis = draw_angle_line(roi, 285, 247, angle, 177)
    cv2.imwrite("angle_visualized.png", vis)
    print("시각화 이미지 저장 완료")