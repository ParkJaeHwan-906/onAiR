import cv2
import os
import numpy as np
from app.ar.feature_extractor import extract_features
from app.ar.feature_tracker import track_features
from app.ar.ransac_filter import ransac_filter
from app.ar.motion_estimator import estimate_motion

# ===== 파라미터 =====
MIN_TRACKS = 60
REFRESH_EVERY = 25
SCALE_FACTOR = 0.3
REVERSE_T = True
Z_ALPHA = 50.0
Z_MIN, Z_MAX = 0.1, 10.0

# --- 전역 상태 (스트리밍용) ---
frame_idx = 0
prev_gray = None
prev_pts = None
current_method = "GFTT"

K_global = None
R_total = np.eye(3, dtype=np.float32)
t_total = np.zeros((3, 1), dtype=np.float32)
prev_t_total = np.zeros((3, 1), dtype=np.float32)  # ← 좌표 스무딩용 이전 상태 저장

last_inlier_old = None
last_inlier_new = None

# 앵커 포인트
anchor_points = []


async def process_frame(frame, sid=None):
    """
    들어온 프레임 단위로 호출됨
    """
    global frame_idx, prev_gray, prev_pts, current_method
    global K_global, R_total, t_total, prev_t_total
    global last_inlier_old, last_inlier_new

    # === 1️⃣ 카메라 보정값 로드 ===
    if K_global is None:
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))  # app/ar/
            calib_path = os.path.join(base_dir, "..", "data", "camera_intrinsics.npy")
            calib_path = os.path.normpath(calib_path)
            K_global = np.load(calib_path)
            print(f"✅ Loaded calibration file: {calib_path}")
        except Exception as e:
            print(f"⚠️ Calibration load failed: {e}")
            return {"status": "no_calib"}

    # === 2️⃣ 그레이 변환 + 히스토그램 평활화 ===
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    # === 3️⃣ 첫 프레임 초기화 ===
    if prev_gray is None:
        prev_gray = gray
        prev_pts, current_method = extract_features(prev_gray)
        return {"status": "init"}

    # === 4️⃣ Optical Flow 추적 ===
    if prev_pts is not None and len(prev_pts) > 0:
        good_prev, good_next, _ = track_features(prev_gray, gray, prev_pts)

        if len(good_prev) >= MIN_TRACKS:
            # 🔹 평균 이동량 계산 (정지 상태 감지)
            flow_magnitude = np.linalg.norm(good_next - good_prev, axis=1).mean()
            if flow_magnitude < 1.5:
                # 거의 움직이지 않으면 좌표 갱신 중단
                return {
                    "status": "static",
                    "x": float(t_total[0, 0]),
                    "y": float(t_total[1, 0]),
                    "z": float(t_total[2, 0]),
                    "flow": flow_magnitude,
                }

            # === 5️⃣ RANSAC 필터 ===
            inlier_prev, inlier_next, _, _ = ransac_filter(good_prev, good_next)
            if inlier_prev is not None and len(inlier_prev) > 8:
                last_inlier_old = inlier_prev.astype(np.float32).copy()
                last_inlier_new = inlier_next.astype(np.float32).copy()

                # === 6️⃣ Essential Matrix 기반 Pose 추정 ===
                R, t, E, stats = estimate_motion(inlier_prev, inlier_next, K_global)
                if stats["pose_ok"]:
                    R_total = R @ R_total
                    step = (R_total @ (t * SCALE_FACTOR))
                    if REVERSE_T:
                        t_total -= step
                    else:
                        t_total += step

                    # 🔹 7️⃣ 좌표 스무딩 (EMA 필터)
                    alpha = 0.1  # smoothing 정도 (0.1~0.3 권장)
                    t_total = alpha * t_total + (1 - alpha) * prev_t_total
                    prev_t_total = t_total.copy()

                    z_val = float(t_total[2, 0])

                    # === 8️⃣ 포인트 업데이트 ===
                    prev_gray = gray.copy()

                    if len(good_next) < MIN_TRACKS:
                        new_pts, _ = extract_features(gray)
                        if new_pts is not None and len(new_pts) > 0:
                            prev_pts = np.vstack((good_next.reshape(-1, 1, 2), new_pts))
                        else:
                            prev_pts = good_next.reshape(-1, 1, 2)
                    else:
                        prev_pts = good_next.reshape(-1, 1, 2)

                    frame_idx += 1

                    return {
                        "status": "ok",
                        "x": float(t_total[0, 0]),
                        "y": float(t_total[1, 0]),
                        "z": z_val,
                        "inliers": len(inlier_prev),
                        "flow": flow_magnitude,
                        "method": current_method,
                    }

    # === 9️⃣ 추적 실패 시 피쳐 리셋 ===
    prev_gray = gray.copy()
    prev_pts, current_method = extract_features(gray)
    frame_idx += 1

    return {"status": "tracking_lost"}
