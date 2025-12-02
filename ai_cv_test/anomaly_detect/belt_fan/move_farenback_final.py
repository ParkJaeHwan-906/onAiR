import cv2, numpy as np, os
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
RESULT_DIR = "results"

def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15, iterations=3,
        poly_n=5, poly_sigma=1.2, flags=0)
    mag, ang = cv2.cartToPolar(flow[...,0], flow[...,1])
    return mag, ang

def classify_state(cur_mag, avg_mag, ratio, delta, prev_state, std_motion):
    delta_norm = delta / (avg_mag + 1e-5)

    # 감속
    if ratio > ACCEL_RATIO and delta_norm > STABLE_TOL:
        state = "E_FAN_SLOWDOWN"
    # 가속
    elif ratio < DECEL_RATIO and delta_norm < -STABLE_TOL and abs(delta) > 1.0:
        state = "E_FAN_ACCELERATE"
    # 정상
    else:
        state = "E_NORMAL"
        
    # 진동 감지 (불규칙 변화)
    if ratio > 1.8 and std_motion > 0.05:
        return "E_FAN_VIBRATION"

    # 이전 상태 유지 보정 (히스테리시스)
    if prev_state == "E_FAN_SLOWDOWN" and ratio > 0.95:
        state = "E_FAN_SLOWDOWN"
    elif prev_state == "E_FAN_ACCELERATE" and ratio < 1.05:
        state = "E_FAN_ACCELERATE"
    elif prev_state == "E_FAN_VIBRATION" and std_motion > 0.04:
        state = "E_FAN_VIBRATION"

    return state

def analyze_video(video_path, show_debug=False):
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

    H, W = prev_gray.shape

    roi_x1 = int(W * 0.05)  # 24
    roi_x2 = int(W * 0.95)  # 456
    
    roi_y1 = int(H * 0.38)  # 137
    roi_y2 = int(H * 0.88)  # 316


    mag_buf, trend_buf, state_hist = deque(maxlen=SMOOTH_WINDOW), deque(maxlen=TREND_WINDOW), deque(maxlen=STATE_SMOOTH)
    prev_state, results, frame_idx = "E_NORMAL", [], 1
    mag_global = []

    print(f"\n영상 분석 시작: {fname} (Resized {RESIZE[0]}x{RESIZE[1]})")

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.resize(frame, RESIZE)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 프레임마다만 Optical Flow 계산
        if frame_idx % 2 == 0:
            roi_prev = prev_gray[roi_y1:roi_y2, roi_x1:roi_x2]
            roi_gray = gray[roi_y1:roi_y2, roi_x1:roi_x2]
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

            if frame_idx <= INIT_IGNORE:
                state = "E_NORMAL"
            else:
                raw = classify_state(smooth_mag, avg_mag, ratio, delta, prev_state, std_motion)
                state_hist.append(raw)
                state = max(Counter(state_hist), key=lambda k: Counter(state_hist)[k])

            prev_state = state
            results.append(state)

            # 프레임별 결과 콘솔 출력
            print(f"Frame {frame_idx:04d}: mag={smooth_mag:.3f}, ratio={ratio:.2f}, std={std_motion:.3f} → {state}")

        # ROI 표시 및 상태 출력 (모든 프레임에)
        color_map = {
            "E_NORMAL": (0,255,0),
            "E_FAN_SLOWDOWN": (0,0,255),
            "E_FAN_ACCELERATE": (255,0,0),
            "E_FAN_VIBRATION": (0,255,255)
        }
        color = color_map.get(prev_state, (255,255,255))
        cv2.rectangle(frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (255,255,0), 2)
        cv2.putText(frame, prev_state, (20,50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
        out.write(frame)

        prev_gray = gray
        frame_idx += 1


    cap.release(); out.release()
    global_avg = np.mean(mag_global)
    cnt, total = Counter(results), max(len(results), 1)
    n, s, a, v = [cnt.get(k, 0) / total * 100 for k in ["E_NORMAL", "E_FAN_SLOWDOWN", "E_FAN_ACCELERATE", "E_FAN_VIBRATION"]]

    # 기존 최다 상태
    dom = max(cnt, key=cnt.get)
    
    # 추가 조건으로 vibration 판정 보정
    if (n <= 20 and abs(s - a) <= 20) or v >= 25: dom = "E_FAN_VIBRATION"
    
    print(f"분석 완료 → {result_path}")
    print(f"평균 흐름 강도: {global_avg:.2f}")
    print(f"요약: NORMAL={n:.1f}% | SLOW={s:.1f}% | ACCEL={a:.1f}% | VIB={v:.1f}% → {dom}\n")
    return {"video":fname,"normal":n,"slow":s,"accel":a,"vib":v,"result":dom}

if __name__=="__main__":
    vdir="fan"
    vids=[os.path.join(vdir,v) for v in os.listdir(vdir) if v.endswith(".mp4")]
    allres=[]
    for p in sorted(vids):
        r=analyze_video(p)
        if r: allres.append(r)
    print("전체 요약 결과")
    for r in allres:
        print(f"{r['video']:<25} → {r['result']} (N:{r['normal']:.1f}% / S:{r['slow']:.1f}% / A:{r['accel']:.1f}% / V:{r['vib']:.1f}%)")
