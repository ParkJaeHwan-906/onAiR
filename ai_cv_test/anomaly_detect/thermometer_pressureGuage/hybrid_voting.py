import numpy as np
import cv2
import math

def hybrid_angle_voting(edge_img, gray_img, center, R,
                        w_edge=1.0, w_dark=2.5,
                        dark_thresh=110):

    h, w = gray_img.shape
    x0, y0 = center

    scores = []

    for ang in range(360):
        theta = np.deg2rad(ang)

        xs = (x0 + np.cos(theta) * np.arange(0, R, 1)).astype(int)
        ys = (y0 - np.sin(theta) * np.arange(0, R, 1)).astype(int)

        valid = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
        xs = xs[valid]
        ys = ys[valid]

        if len(xs) == 0:
            scores.append(0)
            continue

        edge_score = np.sum(edge_img[ys, xs] > 0)
        dark_score = np.sum(gray_img[ys, xs] < dark_thresh)

        hybrid = edge_score * w_edge + dark_score * w_dark
        scores.append(hybrid)

    scores = np.array(scores)
    best_angle = int(np.argmax(scores))
    return best_angle, scores


def draw_angle_line(img, center, angle, length, color=(0,0,255)):
    x0, y0 = center
    theta = np.deg2rad(angle)
    x1 = int(x0 + length * np.cos(theta))
    y1 = int(y0 - length * np.sin(theta))
    out = img.copy()
    cv2.line(out, (x0, y0), (x1, y1), color, 2)
    return out


# -----------------------------
# 실행 예시
# -----------------------------
gray = cv2.imread("debug_step02/01_gray.png", 0)
edge = cv2.imread("debug_step02/03_edges.png", 0)
src = cv2.imread("roi_debug/roi_167_42.png")   # ROI 원본 필요

cx, cy = 285, 247   # ROI 내부 기준 좌표
R = 177

best_angle, scores = hybrid_angle_voting(edge, gray, (cx, cy), R)

result = draw_angle_line(src, (cx, cy), best_angle, R)
cv2.imwrite("angle_result.png", result)
print("best angle:", best_angle)
