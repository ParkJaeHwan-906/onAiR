from ultralytics import YOLO
import cv2, numpy as np, os
from collections import deque, Counter

# ---- YOLO 모델 로드 ----
model = YOLO("-AHU-module-detection-2/runs/train/module_yolo11n/weights/best.pt")

# ---- Hyperparameters ----
RESIZE = (640, 480)
MAG_THRESH = 0.5
SMOOTH_WINDOW = 4
TREND_WINDOW = 10
ACCEL_RATIO = 1.2
DECEL_RATIO = 0.90
STABLE_TOL = 0.15
STATE_SMOOTH = 7
INIT_IGNORE = 8
RESULT_PATH = "fan_optical_flow/belt_motion_tracking_final.mp4"
FRAME_INTERVAL = 30  # YOLO 재탐지 주기

# ---- Optical Flow 계산 ----
def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15, iterations=3,
        poly_n=5, poly_sigma=1.2, flags=0)
    mag, ang = cv2.cartToPolar(flow[...,0], flow[...,1])
    return mag, ang

# ---- 상태 분류 ----
def classify_state(cur_mag, avg_mag, ratio, delta, prev_state, std_motion):
    delta_norm = delta / (avg_mag + 1e-5)

    # 진동 감지
    if ratio > 1.8 and std_motion > 0.05:
        return "E_FAN_VIBRATION"

    # 가속
    if ratio > ACCEL_RATIO and delta_norm > STABLE_TOL:
        state = "E_FAN_ACCELERATE"
    # 감속
    elif ratio < DECEL_RATIO and delta_norm < -STABLE_TOL and abs(delta) > 1.0:
        state = "E_FAN_SLOWDOWN"
    # 정상
    else:
        state = "E_NORMAL"

    # 히스테리시스
    if prev_state == "E_FAN_ACCELERATE" and ratio > 0.95:
        state = "E_FAN_ACCELERATE"
    elif prev_state == "E_FAN_SLOWDOWN" and ratio < 1.05:
        state = "E_FAN_SLOWDOWN"
    elif prev_state == "E_FAN_VIBRATION" and std_motion > 0.04:
        state = "E_FAN_VIBRATION"

    return state


# ---- 메인 루프 ----
video_path = "fan_optical_flow/belt_move.mp4"
cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
print(f"🎥 FPS: {fps}")

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(RESULT_PATH, fourcc, fps, RESIZE)

prev_gray = None
belt_box = None
frame_idx = 0

mag_buf, trend_buf, state_hist = deque(maxlen=SMOOTH_WINDOW), deque(maxlen=TREND_WINDOW), deque(maxlen=STATE_SMOOTH)
prev_state = "E_NORMAL"
results, mag_global = [], []

print("\n🚀 영상 분석 시작")

while True:
    ret, frame = cap.read()
    if not ret: break
    frame_idx += 1
    frame = cv2.resize(frame, RESIZE)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # YOLO 재탐지 주기마다 belt 박스 탐지
    if frame_idx % FRAME_INTERVAL == 1 or belt_box is None:
        preds = model.predict(frame, conf=0.3, verbose=False)
        found_belt = False
        for box in preds[0].boxes:
            cls_name = model.names[int(box.cls)]
            if cls_name == "belt":
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                belt_box = (x1, y1, x2, y2)
                found_belt = True
                print(f"[Frame {frame_idx}] 🎯 벨트 탐지: {belt_box}")
                break

        # 🔸 벨트 미탐지 시 → 분석 중단 (ROI 유지하지 않음)
        if not found_belt:
            belt_box = None
            print(f"[Frame {frame_idx}] ⚠️ 벨트 미탐지 → 분석 스킵")
            prev_gray = gray.copy()
            continue

    # 벨트 박스 없으면 분석 스킵
    if belt_box is None:
        prev_gray = gray.copy()
        continue

    x1, y1, x2, y2 = belt_box
    roi_gray = gray[y1:y2, x1:x2]

    # Optical Flow 계산 (2프레임마다)
    if prev_gray is not None and frame_idx % 2 == 0:
        roi_prev = prev_gray[y1:y2, x1:x2]
        mag, ang = estimate_motion(roi_prev, roi_gray)
        mag_valid = mag[mag > MAG_THRESH]
        mag_mean = np.mean(mag_valid) if mag_valid.size > 0 else 0
        mag_global.append(mag_mean)

        mag_buf.append(mag_mean)
        smooth_mag = np.mean(mag_buf)
        std_motion = np.std(mag_buf)
        trend_buf.append(smooth_mag)
        avg_mag = np.mean(trend_buf)
        ratio = smooth_mag / (avg_mag + 1e-5)
        delta = smooth_mag - avg_mag

        # 상태 분류
        if frame_idx <= INIT_IGNORE:
            state = "E_NORMAL"
        else:
            raw = classify_state(smooth_mag, avg_mag, ratio, delta, prev_state, std_motion)
            state_hist.append(raw)
            state = max(Counter(state_hist), key=lambda k: Counter(state_hist)[k])

        prev_state = state
        results.append(state)
        print(f"[Frame {frame_idx:04d}] mag={smooth_mag:.3f}, ratio={ratio:.2f}, std={std_motion:.3f} → {state}")

        # 표시
        color_map = {
            "E_NORMAL": (0,255,0),
            "E_FAN_SLOWDOWN": (0,0,255),
            "E_FAN_ACCELERATE": (255,0,0),
            "E_FAN_VIBRATION": (0,255,255)
        }
        cv2.rectangle(frame, (x1,y1), (x2,y2), (255,255,0), 2)
        cv2.putText(frame, state, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 1, color_map.get(state, (255,255,255)), 2)

    out.write(frame)
    prev_gray = gray.copy()

cap.release()
out.release()

# ---- 전체 요약 ----
cnt, total = Counter(results), max(len(results), 1)
n,s,a,v = [cnt.get(k,0)/total*100 for k in ["E_NORMAL","E_FAN_SLOWDOWN","E_FAN_ACCELERATE","E_FAN_VIBRATION"]]
dom = max(cnt, key=cnt.get)

# vibration 보정 조건
if (n <= 20 and abs(s - a) <= 20) or v >= 25:
    dom = "E_FAN_VIBRATION"

print("\n✅ Optical Flow + YOLO 통합 분석 완료")
print(f"📊 NORMAL={n:.1f}% | SLOW={s:.1f}% | ACCEL={a:.1f}% | VIB={v:.1f}% → 최종 결과: {dom}")
print(f"💾 결과 저장: {RESULT_PATH}")
