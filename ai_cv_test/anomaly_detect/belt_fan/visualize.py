import cv2
import numpy as np
from collections import deque, Counter
import os

MAG_THRESH = 0.5
SMOOTH_WINDOW = 4
TREND_WINDOW = 10
ACCEL_RATIO = 1.3
DECEL_RATIO = 0.90
STABLE_TOL = 0.3
STATE_SMOOTH = 7
INIT_IGNORE = 8

def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15,
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0
    )
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return flow, mag

def classify_state(cur_mag, avg_mag, ratio, delta, prev_state, std_motion):
    delta_norm = delta / (avg_mag + 1e-5)

    if ratio > ACCEL_RATIO and delta_norm > STABLE_TOL:
        state = "E_FAN_SLOWDOWN"
    elif ratio < DECEL_RATIO and delta_norm < -STABLE_TOL and abs(delta) > 1.0:
        state = "E_FAN_ACCELERATE"
    else:
        state = "E_NORMAL"

    if ratio > 1.8 and std_motion > 0.05:
        return "E_FAN_VIBRATION"

    if prev_state == "E_FAN_SLOWDOWN" and ratio > 0.95:
        state = "E_FAN_SLOWDOWN"
    elif prev_state == "E_FAN_ACCELERATE" and ratio < 1.05:
        state = "E_FAN_ACCELERATE"
    elif prev_state == "E_FAN_VIBRATION" and std_motion > 0.04:
        state = "E_FAN_VIBRATION"

    return state

def visualize_fan_flow(video_path, roi_box, out_path):
    x1, y1, x2, y2 = roi_box

    cap = cv2.VideoCapture(video_path)
    ret, prev = cap.read()
    if not ret:
        print("첫 프레임 실패")
        return

    prev_gray_full = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    prev_gray = prev_gray_full[y1:y2, x1:x2]

    h, w = prev.shape[:2]
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    out = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    mag_buf = deque(maxlen=SMOOTH_WINDOW)
    trend_buf = deque(maxlen=TREND_WINDOW)
    hist = deque(maxlen=STATE_SMOOTH)
    prev_state = "E_NORMAL"
    frame_idx = 1

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = gray_full[y1:y2, x1:x2]

        flow, mag = estimate_motion(prev_gray, gray)
        mag_valid = mag[mag > MAG_THRESH]
        mag_mean = np.mean(mag_valid) if mag_valid.size > 0 else 0

        mag_buf.append(mag_mean)
        smooth_mag = np.mean(mag_buf)
        std_motion = np.std(mag_buf)

        trend_buf.append(smooth_mag)
        avg_mag = np.mean(trend_buf)

        ratio = smooth_mag / (avg_mag + 1e-5)
        delta = smooth_mag - avg_mag

        if frame_idx <= INIT_IGNORE:
            state = "E_NORMAL"
        else:
            raw = classify_state(smooth_mag, avg_mag, ratio, delta, prev_state, std_motion)
            hist.append(raw)
            state = Counter(hist).most_common(1)[0][0]

        prev_state = state

        vis = frame.copy()
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 2)

        step = 15
        fx = flow[..., 0]
        fy = flow[..., 1]
        for yy in range(0, gray.shape[0], step):
            for xx in range(0, gray.shape[1], step):
                dx = fx[yy, xx]
                dy = fy[yy, xx]
                pt1 = (x1 + xx, y1 + yy)
                pt2 = (int(x1 + xx + dx * 5), int(y1 + yy + dy * 5))
                cv2.arrowedLine(vis, pt1, pt2, (255, 255, 255), 1, tipLength=0.3)

        text = f"{state} | mag={smooth_mag:.2f} ratio={ratio:.2f}"
        cv2.putText(vis, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        out.write(vis)
        prev_gray = gray
        frame_idx += 1

    cap.release()
    out.release()
    print(f"저장 완료: {out_path}")


if __name__ == "__main__":
    roi_box = (150, 200, 400, 450)  # 여기를 본인 영상 ROI로 변경

    for p in sorted(os.listdir("fan")):
        if not p.endswith(".mp4"):
            continue

        video_path = os.path.join("fan", p)
        out_path = f"fan_visual_{p}"

        visualize_fan_flow(video_path, roi_box, out_path)
