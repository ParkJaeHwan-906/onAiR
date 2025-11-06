import cv2
import numpy as np

def draw_optical_flow(frame, good_prev, good_next):
    """
    Optical Flow 시각화
    - 이전 프레임에서 현재 프레임으로의 이동 벡터를 표시
    - 초록색 선: 이동 경로
    - 빨간 점: 현재 프레임 위치
    """
    vis = frame.copy()
    for (p1, p2) in zip(good_prev, good_next):
        x1, y1 = p1.ravel()
        x2, y2 = p2.ravel()
        cv2.line(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 1)
        cv2.circle(vis, (int(x2), int(y2)), 2, (0, 0, 255), -1)
    return vis
