import cv2, numpy as np, os
from collections import deque, Counter
from ultralytics import YOLO

# ---- Hyperparameters ----
RESIZE = (640, 480)
MAG_THRESH = 0.5
STOP_THRESH = 0.15         # optical flow 평균이 이 값보다 작으면 정지 상태
SMOOTH_WINDOW = 4
TREND_WINDOW = 10
ACCEL_RATIO = 1.2
DECEL_RATIO = 0.90
STABLE_TOL = 0.15
STATE_SMOOTH = 7
INIT_IGNORE = 8
RESULT_DIR = "belt_optical_flow/yolo_results"


def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15, iterations=3,
        poly_n=5, poly_sigma=1.2, flags=0)
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return mag, ang


def classify_state(cur_mag, avg_mag, ratio, delta, prev_state, std_motion):
    delta_norm = delta / (avg_mag + 1e-5)

    # 완전 정지 상태
    if cur_mag < STOP_THRESH:
        return "E_BELT_STOP"

    # 진동 감지 (불규칙 변화)
    if ratio > 1.8 and std_motion > 0.05:
        return "E_BELT_VIBRATION"

    # 가속
    if ratio > ACCEL_RATIO and delta_norm > STABLE_TOL:
        state = "E_BELT_ACCELERATE"
    # 감속
    elif ratio < DECEL_RATIO and delta_norm < -STABLE_TOL and abs(delta) > 1.0:
        state = "E_BELT_SLOWDOWN"
    # 정상
    else:
        state = "E_NORMAL"

    # 히스테리시스
    if prev_state == "E_BELT_ACCELERATE" and ratio > 0.95:
        state = "E_BELT_ACCELERATE"
    elif prev_state == "E_BELT_SLOWDOWN" and ratio < 1.05:
        state = "E_BELT_SLOWDOWN"
    elif prev_state == "E_BELT_VIBRATION" and std_motion > 0.04:
        state = "E_BELT_VIBRATION"

    return state


def analyze_belt_with_yolo(video_path, yolo_model_path, conf_thresh=0.4):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"영상 열기 실패: {video_path}")
        return None

    model = YOLO(yolo_model_path)
    os.makedirs(RESULT_DIR, exist_ok=True)
    fname = os.path.basename(video_path)
    result_path = os.path.join(RESULT_DIR, f"analyzed_{fname}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    out = cv2.VideoWriter(result_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, RESIZE)

    ret, prev_frame = cap.read()
    if not ret:
        print("첫 프레임 로드 실패")
        return None

    prev_frame = cv2.resize(prev_frame, RESIZE)
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    belts = {}  # belt_id: buffers/state
    frame_idx = 1
    print(f"YOLO 기반 Belt 이상 탐지 시작: {fname}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, RESIZE)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # --- YOLO 탐지 (belt만) ---
        results = model.predict(frame, conf=conf_thresh, device="cpu", verbose=False)
        detections = results[0].boxes
        belt_boxes = []
        for box in detections:
            cls = model.names[int(box.cls)]
            if "belt" in cls.lower():  # belt만 필터링
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                belt_boxes.append((x1, y1, x2, y2))

        if len(belt_boxes) == 0:
            print(f"[Frame {frame_idx:04d}] No belt detected.")
            out.write(frame)
            prev_gray = gray
            frame_idx += 1
            continue

        # --- Optical Flow 분석 ---
        for i, (x1, y1, x2, y2) in enumerate(belt_boxes):
            roi_prev = prev_gray[y1:y2, x1:x2]
            roi_gray = gray[y1:y2, x1:x2]
            if roi_prev.size == 0 or roi_gray.size == 0:
                continue

            mag, ang = estimate_motion(roi_prev, roi_gray)
            mag_valid = mag[mag > MAG_THRESH]
            mag_mean = np.mean(mag_valid) if mag_valid.size > 0 else 0

            if i not in belts:
                belts[i] = {
                    "mag_buf": deque(maxlen=SMOOTH_WINDOW),
                    "trend_buf": deque(maxlen=TREND_WINDOW),
                    "state_hist": deque(maxlen=STATE_SMOOTH),
                    "prev_state": "E_NORMAL",
                    "results": []
                }

            b = belts[i]
            b["mag_buf"].append(mag_mean)
            smooth_mag = np.mean(b["mag_buf"])
            std_motion = np.std(b["mag_buf"])
            b["trend_buf"].append(smooth_mag)
            avg_mag = np.mean(b["trend_buf"])
            ratio = smooth_mag / (avg_mag + 1e-5)
            delta = smooth_mag - avg_mag

            if frame_idx <= INIT_IGNORE:
                state = "E_NORMAL"
            else:
                raw = classify_state(smooth_mag, avg_mag, ratio, delta, b["prev_state"], std_motion)
                b["state_hist"].append(raw)
                state = max(Counter(b["state_hist"]), key=lambda k: Counter(b["state_hist"])[k])

            b["prev_state"] = state
            b["results"].append(state)

            # --- 콘솔 출력 ---
            print(f"[Frame {frame_idx:04d}] Belt#{i}: mag={smooth_mag:.3f}, ratio={ratio:.2f}, std={std_motion:.3f} → {state}")

            # --- 영상 표시 ---
            color_map = {
                "E_NORMAL": (0, 255, 0),
                "E_BELT_SLOWDOWN": (0, 0, 255),
                "E_BELT_ACCELERATE": (255, 0, 0),
                "E_BELT_VIBRATION": (0, 255, 255),
                "E_BELT_STOP": (180, 180, 180)
            }
            color = color_map.get(state, (255, 255, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, state, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        out.write(frame)
        prev_gray = gray
        frame_idx += 1

    cap.release()
    out.release()
    print(f"저장 완료: {result_path}")

    # --- 요약 결과 ---
    summary = {}
    for bid, b in belts.items():
        cnt, total = Counter(b["results"]), max(len(b["results"]), 1)
        n, s, a, v, st = [cnt.get(k, 0)/total*100 for k in
                          ["E_NORMAL", "E_BELT_SLOWDOWN", "E_BELT_ACCELERATE", "E_BELT_VIBRATION", "E_BELT_STOP"]]
        dom = max(cnt, key=cnt.get)
        if (n <= 20 and abs(s - a) <= 20) or v >= 25:
            dom = "E_BELT_VIBRATION"
        summary[bid] = dict(normal=n, slow=s, accel=a, vib=v, stop=st, result=dom)
        print(f"Belt#{bid}: N={n:.1f}% | S={s:.1f}% | A={a:.1f}% | V={v:.1f}% | STOP={st:.1f}% → {dom}")

    return summary


if __name__ == "__main__":
    video_path = "fan_optical_flow/motion/belt_move.mp4"
    yolo_model = "-AHU-module-detection-2/runs/train/module_yolo11n/weights/best.pt"
    analyze_belt_with_yolo(video_path, yolo_model)
