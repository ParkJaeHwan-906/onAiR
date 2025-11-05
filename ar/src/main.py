# 📄 main.py — 안정형 단일 카메라 AR (GFTT↔ORB 자동 대응)
import cv2
import numpy as np
import os

from video_loader import load_video
from feature_extractor import extract_features
from feature_tracker import track_features
from ransac_filter import ransac_filter
from motion_estimator import estimate_motion

# ===== 파라미터 =====
MIN_TRACKS      = 60
REFRESH_EVERY   = 25
DISPLAY_SCALE   = 0.8
CALIB_PATH      = "../data/camera_intrinsics.npy"
DIST_PATH       = "../data/dist_coeffs.npy"
SCALE_FACTOR    = 0.3
REVERSE_T       = True
Z_ALPHA         = 50.0
Z_MIN, Z_MAX    = 0.1, 10.0

# --- 전역 상태 ---
anchor_points = []  # (x, y, z)
K_global = None
R_total = np.eye(3, dtype=np.float32)
t_total = np.zeros((3, 1), dtype=np.float32)
last_inlier_old = None
last_inlier_new = None
current_method = "GFTT"


# 🖱️ 마우스 클릭 → 앵커 추가 (+ z 근사)
def mouse_click(event, x_disp, y_disp, flags, param):
    global anchor_points, last_inlier_old, last_inlier_new, K_global

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    x = int(x_disp / DISPLAY_SCALE)
    y = int(y_disp / DISPLAY_SCALE)
    z = 1.0

    if last_inlier_old is not None and last_inlier_new is not None and K_global is not None:
        pts_old = last_inlier_old.reshape(-1, 2)
        pts_new = last_inlier_new.reshape(-1, 2)

        if len(pts_old) > 0:
            d2 = np.sum((pts_old - np.array([x, y], dtype=np.float32))**2, axis=1)
            idx = int(np.argmin(d2))
            flow_vec = pts_new[idx] - pts_old[idx]
            flow_len = float(np.linalg.norm(flow_vec))

            fx, fy = K_global[0, 0], K_global[1, 1]
            f = (fx + fy) / 2.0
            z = (Z_ALPHA * (f / 1000.0)) / (flow_len + 1e-3)
            z = float(np.clip(z, Z_MIN, Z_MAX * 3))

    anchor_points.append(np.array([[x, y, z]], dtype=np.float32))
    print(f"📍 z≈{z:.3f}")


# 🎯 3D → 2D 투영
def project_point(world_point, R, t, K, frame_shape):
    h, w = frame_shape[:2]
    cam_point = R @ world_point + t
    if cam_point[2, 0] <= 1e-6:
        return None
    proj = K @ cam_point
    proj /= proj[2, 0]
    px, py = int(proj[0, 0]), int(proj[1, 0])
    if 0 <= px < w and 0 <= py < h:
        return px, py
    return None


# 🚀 메인 루프
def main():
    global K_global, R_total, t_total, last_inlier_old, last_inlier_new, current_method

    video = load_video("../data/3.mp4")
    K_global = np.load(CALIB_PATH) if os.path.exists(CALIB_PATH) else None
    use_pose = K_global is not None

    win_name = "Pose & Anchor View"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win_name, mouse_click)

    ret, prev_frame = video.read()
    if not ret:
        return

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_pts, current_method = extract_features(prev_gray)
    print(f"🔍 Initial feature method: {current_method} ({len(prev_pts)} pts)")
    frame_idx = 0

    while True:
        ret, frame = video.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # === 주기적 특징점 갱신 ===
        if REFRESH_EVERY and frame_idx > 0 and frame_idx % REFRESH_EVERY == 0:
            prev_pts, current_method = extract_features(prev_gray)
            print(f"🔄 Refresh features using {current_method} ({len(prev_pts)} pts)")

        # === Optical Flow 추적 ===
        if prev_pts is not None and len(prev_pts) > 0:
            good_prev, good_next, _ = track_features(prev_gray, gray, prev_pts)
            if len(good_prev) >= MIN_TRACKS:
                # RANSAC 필터
                inlier_prev, inlier_next, _, _ = ransac_filter(good_prev, good_next)
                if inlier_prev is not None and len(inlier_prev) > 8:
                    last_inlier_old = inlier_prev.astype(np.float32).copy()
                    last_inlier_new = inlier_next.astype(np.float32).copy()

                    # Essential Matrix 기반 Pose 추정
                    if use_pose:
                        R, t, E, stats = estimate_motion(inlier_prev, inlier_next, K_global)
                        if stats["pose_ok"]:
                            R_total = R @ R_total
                            step = (R_total @ (t * SCALE_FACTOR))
                            if REVERSE_T:
                                t_total -= step
                            else:
                                t_total += step

                            z_val = float(t_total[2, 0])
                            # print(f"[{current_method}] z={z_val:.3f}, parallax={stats['parallax_px']:.2f}px, "
                            #       f"inliers={stats['in_pts']}, cheirality={stats['cheirality_ratio']:.2f}")

        # === 앵커 투영 ===
        if use_pose and len(anchor_points) > 0:
            for anchor in anchor_points:
                pixel = np.array([[anchor[0][0]], [anchor[0][1]], [1.0]], dtype=np.float32)
                world_point = np.linalg.inv(K_global).astype(np.float32) @ pixel
                world_point *= float(anchor[0][2])
                proj = project_point(world_point, R_total, t_total, K_global, frame.shape)
                if proj is not None:
                    color = (0, 255, 0) if current_method == "GFTT" else (0, 255, 255)
                    cv2.circle(frame, proj, 8, color, -1)

        # === 디스플레이 ===
        disp = cv2.resize(frame, (int(frame.shape[1]*DISPLAY_SCALE), int(frame.shape[0]*DISPLAY_SCALE)))
        cv2.putText(
            disp, f"Method: {current_method}", (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0) if current_method == "GFTT" else (0, 255, 255), 2
        )
        cv2.imshow(win_name, disp)

        key = cv2.waitKey(20) & 0xFF
        if key == ord('q'):
            break

        prev_gray = gray.copy()
        prev_pts = extract_features(gray)[0] if len(good_next) < MIN_TRACKS else good_next.reshape(-1, 1, 2)
        frame_idx += 1

    video.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
