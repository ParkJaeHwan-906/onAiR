import cv2, numpy as np, os
from ultralytics import YOLO
from collections import deque, Counter

# ---- Hyperparameters ----
RESIZE = (480, 360)
MAG_THRESH = 0.5
SMOOTH_WINDOW = 4
TREND_WINDOW = 10
ACCEL_RATIO = 1.3
DECEL_RATIO = 0.90
STABLE_TOL = 0.3
STATE_SMOOTH = 7
INIT_IGNORE = 8
RESULT_DIR = "yolo_results"
CONF_THRESH = 0.2

# ONLY CHANGE: YOLO 모델 불러오기
model = YOLO("final_v2.pt")

def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15, iterations=3,
        poly_n=5, poly_sigma=1.2, flags=0)
    mag, ang = cv2.cartToPolar(flow[...,0], flow[...,1])
    return mag

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

def analyze_video(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"영상 열기 실패: {video_path}")
        return None

    os.makedirs(RESULT_DIR, exist_ok=True)
    fname = os.path.basename(video_path)
    result_path = os.path.join(RESULT_DIR, f"analyzed_{fname}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    out = cv2.VideoWriter(result_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, RESIZE)

    ret, prev_frame = cap.read()
    if not ret:
        print(f"첫 프레임 실패: {video_path}")
        return None

    prev_frame = cv2.resize(prev_frame, RESIZE)
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    detections = model.predict(prev_frame, conf=CONF_THRESH, verbose=False)[0].boxes
    rois = []  # [(x1,y1,x2,y2)]
    for b in detections:
        cls = model.names[int(b.cls)].lower()
        if ("fan" in cls) or ("belt" in cls):
            x1,y1,x2,y2 = map(int,b.xyxy[0])
            rois.append((x1,y1,x2,y2))

    if not rois:
        print("YOLO ROI 없음 → 영상 그대로 저장")
        return None

    mag_buf, trend_buf = deque(maxlen=SMOOTH_WINDOW), deque(maxlen=TREND_WINDOW)
    state_hist = deque(maxlen=STATE_SMOOTH)
    prev_state, results = "E_NORMAL", []
    frame_idx = 1
    mag_global = []

    print(f"\n영상 분석 시작: {fname} (Resized {RESIZE[0]}x{RESIZE[1]})")

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.resize(frame, RESIZE)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if frame_idx % 2 == 0:
            # 여러 ROI → 평균
            mag_list = []
            for (x1,y1,x2,y2) in rois:
                roi_prev = prev_gray[y1:y2, x1:x2]
                roi_gray = gray[y1:y2, x1:x2]
                if roi_prev.size == 0: continue
                mag = estimate_motion(roi_prev, roi_gray)
                mag_valid = mag[mag > MAG_THRESH]
                if mag_valid.size > 0:
                    mag_list.append(np.mean(mag_valid))

            mag_mean = np.mean(mag_list) if mag_list else 0

            mag_global.append(mag_mean)
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
                raw = classify_state(smooth_mag, avg_mag, ratio,
                                    delta, prev_state, std_motion)
                state_hist.append(raw)
                state = max(state_hist, key=state_hist.count)

            prev_state = state
            results.append(state)

            print(f"Frame {frame_idx:04d}: mag={smooth_mag:.3f}, ratio={ratio:.2f} → {state}")

        # 박스 & 상태 표시 (매 프레임)
        color_map = {
            "E_NORMAL": (0,255,0),
            "E_FAN_SLOWDOWN": (0,0,255),
            "E_FAN_ACCELERATE": (255,0,0),
            "E_FAN_VIBRATION": (0,255,255)
        }
        color = color_map.get(prev_state, (255,255,255))

        for (x1,y1,x2,y2) in rois:
            cv2.rectangle(frame, (x1,y1),(x2,y2), (255,255,0), 2)

        cv2.putText(frame, prev_state, (20,50), cv2.FONT_HERSHEY_SIMPLEX,
                    1.2, color, 3)
        out.write(frame)

        prev_gray = gray
        frame_idx += 1

    cap.release()
    out.release()

    print(f"저장 완료 → {result_path}")
    return True


if __name__ == "__main__":
    vdir = "fan"
    vids = [os.path.join(vdir, v)
            for v in os.listdir(vdir) if v.endswith(".mp4")]

    for p in sorted(vids):
        analyze_video(p)

    print("\n=== 전체 처리 완료 ===")
