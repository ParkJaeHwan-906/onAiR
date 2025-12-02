import cv2
import numpy as np
import os
from collections import deque

# =====================
# 🔧 Hyperparameters
# =====================
EMA_ALPHA = 0.35        # 이동 평균 반영 비율 (값↑ → 반응 빠름)
STOP_THRESHOLD = 0.05   # 평균 이동량이 이보다 작으면 정지로 간주
ACCEL_RATIO = 1.25      # 가속 판단 비율
DECEL_RATIO = 0.8       # 감속 판단 비율
BRIGHTNESS_TH = 15      # 밝기 변화 감쇠 임계값
ANGLE_STD_TH = 1.5      # 방향 일관성(불규칙성) 임계값
BASELINE_FRAMES = 50    # 기준선 계산용 프레임 수
WINDOW = 10             # 이동평균 윈도우

# =====================
# 이벤트 정의
# =====================
E_NORMAL = "E_NORMAL"
E_ACCEL = "E_FAN_ACCELERATE"
E_DECEL = "E_FAN_SLOWDOWN"
E_VIB = "E_PATTERN_BREAK"

# =====================
# Optical Flow 분석
# =====================
def analyze_video(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] 영상 열기 실패: {video_path}")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    os.makedirs("fan_optical_flow/results", exist_ok=True)
    out_path = f"fan_optical_flow/results/analyzed_{os.path.basename(video_path)}"
    out = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (640, 480))

    print(f"\n▶ 영상 분석 시작: {os.path.basename(video_path)} (Resized 640x480)")

    ret, prev = cap.read()
    if not ret:
        print("[ERROR] 첫 프레임 읽기 실패")
        return None

    prev = cv2.resize(prev, (640, 480))
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    mag_hist = deque(maxlen=WINDOW)
    baseline_vals = []
    result_counts = {E_NORMAL: 0, E_ACCEL: 0, E_DECEL: 0, E_VIB: 0}
    frame_idx = 0
    baseline = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        frame = cv2.resize(frame, (640, 480))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # --- Optical Flow 계산 ---
        flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None,
                                            pyr_scale=0.5, levels=3, winsize=15,
                                            iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        mag_mean = np.mean(mag)

        # (1) 방향 일관성 기반 필터링
        angle_std = np.std(ang)
        if angle_std > ANGLE_STD_TH:
            prev_gray = gray
            continue  # 조명 반사 등 불규칙 → skip

        # (2) 밝기 변화 감쇠
        brightness_change = abs(np.mean(gray) - np.mean(prev_gray))
        if brightness_change > BRIGHTNESS_TH:
            mag_mean *= 0.5

        # (3) 기준선 보정
        if frame_idx <= BASELINE_FRAMES:
            baseline_vals.append(mag_mean)
            baseline = np.mean(baseline_vals)
        ratio = mag_mean / (baseline + 1e-6) if baseline else 1.0

        # --- EMA (지수 이동 평균)
        if frame_idx == 1:
            smooth_mag = mag_mean
        else:
            smooth_mag = EMA_ALPHA * mag_mean + (1 - EMA_ALPHA) * smooth_mag

        mag_hist.append(smooth_mag)
        delta = smooth_mag - np.mean(mag_hist)

        # --- 판정 로직 ---
        if smooth_mag < STOP_THRESHOLD:
            event = E_NORMAL
        elif ratio > ACCEL_RATIO:
            event = E_ACCEL
        elif ratio < DECEL_RATIO:
            event = E_DECEL
        else:
            event = E_NORMAL

        result_counts[event] += 1

        print(f"[{os.path.basename(video_path)} | F{frame_idx:03d}] "
              f"mag={smooth_mag:.3f}, Δ={delta:.3f}, r={ratio:.2f}, "
              f"brightΔ={brightness_change:.1f}, ang_std={angle_std:.2f} → {event}")

        cv2.putText(frame, event, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,0), 2)
        out.write(frame)
        prev_gray = gray.copy()

    cap.release()
    out.release()

    # --- 결과 요약 ---
    total = sum(result_counts.values())
    result_pct = {k: (v / total) * 100 for k, v in result_counts.items()}
    dominant = max(result_counts, key=result_counts.get)
    print(f"분석 완료 → {out_path}")
    print(f"요약: NORMAL={result_pct[E_NORMAL]:.1f}% | SLOW={result_pct[E_DECEL]:.1f}% | "
          f"ACCEL={result_pct[E_ACCEL]:.1f}% | VIB={result_pct[E_VIB]:.1f}% → 최종: {dominant}\n")

    return {
        "video": os.path.basename(video_path),
        "result": dominant,
        "normal": result_pct[E_NORMAL],
        "slow": result_pct[E_DECEL],
        "accel": result_pct[E_ACCEL],
        "vib": result_pct[E_VIB],
    }


# =====================
# 메인 실행
# =====================
def main():
    base_dir = "fan_optical_flow/motion"
    video_files = [f for f in os.listdir(base_dir) if f.endswith(".mp4")]
    all_results = []

    for v in video_files:
        path = os.path.join(base_dir, v)
        res = analyze_video(path)
        if res:
            all_results.append(res)

    print("\n📦 전체 요약 결과")
    for r in all_results:
        print(f"{r['video']:<25} → {r['result']} "
              f"(N:{r['normal']:.1f}% / S:{r['slow']:.1f}% / A:{r['accel']:.1f}% / V:{r['vib']:.1f}%)")


if __name__ == "__main__":
    main()
