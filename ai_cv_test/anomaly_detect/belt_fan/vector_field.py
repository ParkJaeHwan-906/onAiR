import cv2
import numpy as np

def draw_optical_flow_arrows(gray_prev, gray, step=10):
    # Optical Flow 계산
    flow = cv2.calcOpticalFlowFarneback(
        gray_prev, gray, None,
        pyr_scale=0.5, levels=3, winsize=15,
        iterations=3, poly_n=5, poly_sigma=1.1,
        flags=0
    )

    h, w = gray.shape
    vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # 화살표 시각화
    for y in range(0, h, step):
        for x in range(0, w, step):
            fx, fy = flow[y, x]
            end_x = int(x + fx * 5)
            end_y = int(y + fy * 5)
            cv2.arrowedLine(
                vis,
                (x, y),
                (end_x, end_y),
                (0, 0, 255),   # 화살표 색
                1,
                tipLength=0.3
            )

    return vis


# -------------------------------
# ✔ 영상 처리 및 이미지 저장
# -------------------------------

video_path = "./fan/normal_13fps.mp4"
save_dir = "./flow"
step = 12

cap = cv2.VideoCapture(video_path)

ret, frame_prev = cap.read()
if not ret:
    raise RuntimeError("첫 프레임을 읽지 못했습니다.")

prev_gray = cv2.cvtColor(frame_prev, cv2.COLOR_BGR2GRAY)
frame_idx = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    vis = draw_optical_flow_arrows(prev_gray, gray, step=step)

    # 이미지 저장
    out_path = f"{save_dir}/flow_{frame_idx:04d}.jpg"
    cv2.imwrite(out_path, vis)

    prev_gray = gray
    frame_idx += 1

cap.release()
