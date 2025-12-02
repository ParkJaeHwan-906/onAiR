import cv2, numpy as np, os
from collections import deque, Counter

# ---- Hyperparameters ----
RESIZE = (640, 480)          # 해상도 통일
MAG_THRESH = 0.5             # 작은 흐름 제거 기준
SMOOTH_WINDOW = 5            # 단기 이동평균 프레임 수
TREND_WINDOW = 15            # 추세 판단용 프레임 수
ACCEL_RATIO = 1.25           # 평균 대비 가속 인식 비율
DECEL_RATIO = 0.80           # 평균 대비 감속 인식 비율
STABLE_TOL = 0.2             # 안정 구간 허용 오차
STATE_SMOOTH = 7             # 최근 n프레임 다수결로 상태 안정화
INIT_IGNORE = 8              # 초기 안정화 프레임
FRAME_STEP = 2  
RESULT_DIR = "fan_optical_flow/results"

def estimate_motion(prev_gray, gray):
    flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None,
        pyr_scale=0.5, levels=3, winsize=15, iterations=3,
        poly_n=5, poly_sigma=1.2, flags=0)
    mag, ang = cv2.cartToPolar(flow[...,0], flow[...,1])
    return mag, ang

def classify_state(cur_mag, avg_mag, ratio, delta, prev_state):
    if ratio > ACCEL_RATIO and delta > STABLE_TOL:
        state = "E_FAN_ACCELERATE"
    elif ratio < DECEL_RATIO and delta < -STABLE_TOL:
        state = "E_FAN_SLOWDOWN"
    else:
        state = "E_NORMAL"
    if prev_state == "E_FAN_ACCELERATE" and ratio > 0.9:
        state = "E_FAN_ACCELERATE"
    elif prev_state == "E_FAN_SLOWDOWN" and ratio < 1.1:
        state = "E_FAN_SLOWDOWN"
    return state

def analyze_video(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ 영상 열기 실패: {video_path}")
        return None
    os.makedirs(RESULT_DIR, exist_ok=True)
    fname = os.path.basename(video_path)
    result_path = os.path.join(RESULT_DIR, f"analyzed_{fname}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    out = cv2.VideoWriter(result_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, RESIZE)

    ret, prev_frame = cap.read()
    if not ret:
        print(f"❌ 첫 프레임 실패: {video_path}")
        return None
    prev_frame = cv2.resize(prev_frame, RESIZE)
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    mag_buf, trend_buf, state_hist = deque(maxlen=SMOOTH_WINDOW), deque(maxlen=TREND_WINDOW), deque(maxlen=STATE_SMOOTH)
    prev_state, results, frame_idx = "E_NORMAL", [], 1
    print(f"\n▶ 영상 분석 시작: {fname} (Resized {RESIZE[0]}x{RESIZE[1]})")

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.resize(frame, RESIZE)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mag,_ = estimate_motion(prev_gray, gray)
        prev_gray = gray

        mag_valid = mag[mag > MAG_THRESH]
        mag_mean = np.mean(mag_valid) if mag_valid.size > 0 else 0
        mag_buf.append(mag_mean)
        smooth_mag = np.mean(mag_buf)
        trend_buf.append(smooth_mag)
        avg_mag = np.mean(trend_buf)
        ratio = smooth_mag / (avg_mag + 1e-5)
        delta = smooth_mag - avg_mag

        if frame_idx <= INIT_IGNORE:
            state = "E_NORMAL"
        else:
            raw = classify_state(smooth_mag, avg_mag, ratio, delta, prev_state)
            state_hist.append(raw)
            state = max(Counter(state_hist), key=lambda k: Counter(state_hist)[k])
        prev_state = state
        results.append(state)

        print(f"[{fname} | F{frame_idx:03}] mag={smooth_mag:.3f}, Δ={delta:.3f}, r={ratio:.2f} → {state}")
        color = (0,255,0) if state=="E_NORMAL" else ((0,0,255) if state=="E_FAN_SLOWDOWN" else (255,0,0))
        cv2.putText(frame, state, (20,50), cv2.FONT_HERSHEY_SIMPLEX,1.2,color,3)
        out.write(frame)
        frame_idx += 1

    cap.release(); out.release()
    cnt, total = Counter(results), max(len(results),1)
    n,s,a = [cnt.get(k,0)/total*100 for k in ["E_NORMAL","E_FAN_SLOWDOWN","E_FAN_ACCELERATE"]]
    dom = max(cnt, key=cnt.get)
    print(f"✅ 분석 완료 → {result_path}")
    print(f"📊 요약: NORMAL={n:.1f}% | SLOW={s:.1f}% | ACCEL={a:.1f}% → {dom}\n")
    return {"video":fname,"normal":n,"slow":s,"accel":a,"result":dom}

if __name__=="__main__":
    vdir="fan_optical_flow/motion"
    vids=[os.path.join(vdir,v) for v in os.listdir(vdir) if v.endswith(".mp4")]
    allres=[]
    for p in sorted(vids):
        r=analyze_video(p)
        if r: allres.append(r)
    print("📦 전체 요약 결과")
    for r in allres:
        print(f"{r['video']:<25} → {r['result']} (N:{r['normal']:.1f}% / S:{r['slow']:.1f}% / A:{r['accel']:.1f}%)")