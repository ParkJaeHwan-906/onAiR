# 📄 main.py — 깔끔 로그 버전 (z값만 콘솔 출력)
import cv2
import numpy as np
import os

from video_loader import load_video
from feature_extractor import extract_features
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


# 🖱️ 마우스 클릭 → 앵커 추가 (+ z 근사)
def mouse_click(event, x_disp, y_disp, flags, param):
    global anchor_points, last_inlier_old, last_inlier_new

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    # 리사이즈된 창 좌표 → 원본 좌표 복원
    x = int(x_disp / DISPLAY_SCALE)
    y = int(y_disp / DISPLAY_SCALE)
    z = 1.0

    # 최근 Optical Flow 인라이어 기반 z 근사
    if last_inlier_old is not None and last_inlier_new is not None:
        pts_old = last_inlier_old.reshape(-1, 2)
        pts_new = last_inlier_new.reshape(-1, 2)
        if len(pts_old) > 0:
            d2 = np.sum((pts_old - np.array([x, y], dtype=np.float32))**2, axis=1)
            idx = int(np.argmin(d2))
            flow_vec = pts_new[idx] - pts_old[idx]
            flow_len = float(np.linalg.norm(flow_vec))
            z = Z_ALPHA / (flow_len + 1e-3)
            z = float(np.clip(z, Z_MIN, Z_MAX))

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
    global K_global, R_total, t_total, last_inlier_old, last_inlier_new

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
    prev_pts = extract_features(prev_gray)
    frame_idx = 0

    while True:
        ret, frame = video.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if REFRESH_EVERY and frame_idx > 0 and frame_idx % REFRESH_EVERY == 0:
            prev_pts = extract_features(prev_gray)

        if prev_pts is not None and len(prev_pts) > 0:
            next_pts, status, err = cv2.calcOpticalFlowPyrLK(
                prev_gray, gray, prev_pts, None,
                winSize=(21, 21), maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
            )
            if next_pts is not None and status is not None:
                good_new = next_pts[status.flatten() == 1]
                good_old = prev_pts[status.flatten() == 1]
                if len(good_new) >= MIN_TRACKS:
                    inlier_prev, inlier_next, _, _ = ransac_filter(good_old, good_new)
                    if inlier_prev is not None and len(inlier_prev) > 0:
                        last_inlier_old = inlier_prev.astype(np.float32).copy()
                        last_inlier_new = inlier_next.astype(np.float32).copy()
                        if use_pose and len(inlier_prev) >= 8:
                            R, t, _ = estimate_motion(inlier_prev, inlier_next, K_global)
                            if R is not None and t is not None:
                                R_total = R @ R_total
                                step = (R_total @ (t * SCALE_FACTOR))
                                if REVERSE_T:
                                    t_total -= step
                                else:
                                    t_total += step

        # 앵커 투영 및 표시
        if use_pose and len(anchor_points) > 0:
            for i, anchor in enumerate(anchor_points):
                pixel = np.array([[anchor[0][0]], [anchor[0][1]], [1.0]], dtype=np.float32)
                world_point = np.linalg.inv(K_global).astype(np.float32) @ pixel
                world_point *= float(anchor[0][2])
                proj = project_point(world_point, R_total, t_total, K_global, frame.shape)
                if proj is not None:
                    px, py = proj
                    cv2.circle(frame, (px, py), 8, (0, 255, 0), -1)

        disp = cv2.resize(frame, (int(frame.shape[1]*DISPLAY_SCALE), int(frame.shape[0]*DISPLAY_SCALE)))
        cv2.imshow(win_name, disp)

        if cv2.waitKey(20) & 0xFF == ord('q'):
            break

        prev_gray = gray.copy()
        prev_pts = next_pts if 'next_pts' in locals() and next_pts is not None else extract_features(gray)
        frame_idx += 1

    video.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
