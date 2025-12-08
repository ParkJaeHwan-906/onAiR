import cv2
import numpy as np
import os
from collections import deque, Counter

# 하이퍼파라미터
FLOW_STEP = 8                  # 광류 계산 간격 (8픽셀마다 샘플링)
MAG_THRESH = 1.0               # 유효한 흐름 크기 하한값 (잡음 제거용)
SMOOTH_WINDOW = 7              # 단기 평균화 윈도우(움직임 안정화)
ACC_WINDOW = 12                # 가속 판단용 장기 평균화 윈도우
DECEL_RATIO = 0.85             # 감속 판단 비율 (이전 대비 얼마나 줄면 감속으로 볼지)
ACCEL_RATIO = 1.15             # 가속 판단 비율 (이전 대비 얼마나 늘면 가속으로 볼지)
SLOW_FREQ_THRESH = 0.35        # 회전수 기준으로 느린 상태로 보는 하한선
FAST_FREQ_THRESH = 0.75        # 회전수 기준으로 빠른 상태로 보는 상한선
STABLE_TOL = 0.10              # 안정 구간 허용 오차 (Δmag 허용 범위)
INIT_IGNORE_FRAMES = 5         # 초기 프레임 무시 (광류 안정화 구간)
STATE_SMOOTH = 7               # 상태 다수결 안정화 (최근 n프레임 기준)
RESULT_DIR = "fan_optical_flow/results"

def estimate_motion(prev_gray, gray):
    """Optical Flow 계산"""
    flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None,
                                        pyr_scale=0.5, levels=3,
                                        winsize=15, iterations=3,
                                        poly_n=5, poly_sigma=1.2, flags=0)
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return mag, ang

def estimate_freq(angles, window=30):
    """회전 주기 기반 회전수 추정"""
    if len(angles) < 2:
        return 0.0
    diff = np.diff(np.unwrap(angles))
    large_turns = np.sum(np.abs(diff) > 0.2)
    freq = large_turns / max(len(diff), 1)
    return np.clip(freq, 0, 1.0)

def classify_state(mag_mean, mag_ratio, delta_mag, freq, prev_state):
    """상태 분류 로직"""
    # 비정상 값 방어: ratio가 튀면 1.0으로 클리핑
    mag_ratio = np.clip(mag_ratio, 0.5, 2.0)

    # 감속
    if (mag_ratio < DECEL_RATIO and delta_mag < -STABLE_TOL) or freq < SLOW_FREQ_THRESH:
        state = "E_FAN_SLOWDOWN"
    # 가속
    elif (mag_ratio > ACCEL_RATIO or delta_mag > STABLE_TOL * 2) and mag_mean > 3:
        state = "E_FAN_ACCELERATE"
    else:
        state = "E_NORMAL"

    # 히스테리시스(상태 지속 강화)
    if prev_state == "E_FAN_ACCELERATE" and mag_ratio > 0.95:
        state = "E_FAN_ACCELERATE"
    elif prev_state == "E_FAN_SLOWDOWN" and mag_ratio < 1.05:
        state = "E_FAN_SLOWDOWN"

    return state


def analyze_video(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ 영상 열기 실패: {video_path}")
        return None

    os.makedirs(RESULT_DIR, exist_ok=True)
    filename = os.path.basename(video_path)
    result_path = os.path.join(RESULT_DIR, f"analyzed_{filename}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 20
    width, height = map(int, [cap.get(3), cap.get(4)])
    out = cv2.VideoWriter(result_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

    ret, prev_frame = cap.read()
    if not ret:
        print(f"❌ 첫 프레임 읽기 실패: {video_path}")
        return None
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    mag_history, acc_history, angle_history = deque(maxlen=SMOOTH_WINDOW), deque(maxlen=ACC_WINDOW), deque(maxlen=60)
    state_history = deque(maxlen=STATE_SMOOTH)
    results = []
    prev_state = "E_NORMAL"
    frame_idx = 1

    print(f"\n▶ 영상 분석 시작: {filename}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mag, ang = estimate_motion(prev_gray, gray)
        prev_gray = gray

        mag_valid = mag[mag > MAG_THRESH]
        mag_mean = np.mean(mag_valid) if mag_valid.size > 0 else 0
        mag_history.append(mag_mean)
        smooth_mean = np.mean(mag_history)
        acc_history.append(smooth_mean)

        if len(acc_history) > 3:
            prev_mean = np.mean(list(acc_history)[:-1])
            mag_ratio = smooth_mean / (prev_mean + 1e-5)
            delta_mag = smooth_mean - prev_mean
        else:
            mag_ratio, delta_mag = 1.0, 0.0

        angle_history.append(np.mean(ang))
        freq = estimate_freq(list(angle_history))

        # 초기 안정화 구간 무시
        if frame_idx <= INIT_IGNORE_FRAMES:
            state = "E_NORMAL"
        else:
            raw_state = classify_state(smooth_mean, mag_ratio, delta_mag, freq, prev_state)
            state_history.append(raw_state)
            # 최근 n프레임 다수결
            cnt = Counter(state_history)
            state = max(cnt, key=cnt.get)

        prev_state = state
        results.append(state)

        # 로그
        print(f"[{filename} | Frame {frame_idx:03}] mean={smooth_mean:.2f}, Δ={mag_ratio:.2f}, Δmag={delta_mag:.2f}, freq={freq:.2f} → {state}")

        # 시각화
        color = (0, 255, 0) if state == "E_NORMAL" else ((0, 0, 255) if state == "E_FAN_SLOWDOWN" else (255, 0, 0))
        cv2.putText(frame, f"{state}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 3)
        out.write(frame)
        frame_idx += 1

    cap.release()
    out.release()

    count = Counter(results)
    total = sum(count.values())
    normal_rate = count.get("E_NORMAL", 0) / total * 100
    slow_rate = count.get("E_FAN_SLOWDOWN", 0) / total * 100
    accel_rate = count.get("E_FAN_ACCELERATE", 0) / total * 100
    dominant = max(count, key=count.get)

    print(f"✅ 분석 완료 → {result_path}")
    print(f"📊 최종 요약: NORMAL={normal_rate:.1f}% | SLOWDOWN={slow_rate:.1f}% | ACCEL={accel_rate:.1f}% → 🏁 {dominant}\n")

    return {"video": filename, "normal": normal_rate, "slow": slow_rate, "accel": accel_rate, "result": dominant}


if __name__ == "__main__":
    video_dir = "fan_optical_flow/motion"
    videos = [os.path.join(video_dir, v) for v in os.listdir(video_dir) if v.endswith(".mp4")]

    all_results = []
    for video_path in sorted(videos):
        result = analyze_video(video_path)
        if result:
            all_results.append(result)

    print("📦 전체 요약 결과")
    for r in all_results:
        print(f"{r['video']:<25} → {r['result']} "
              f"(N:{r['normal']:.1f}% / S:{r['slow']:.1f}% / A:{r['accel']:.1f}%)")
