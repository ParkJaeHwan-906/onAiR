# 📄 main.py — 클릭시 z를 삼각측량으로 추정
import cv2
import numpy as np
import os

from video_loader import load_video
from feature_extractor import extract_features
from ransac_filter import ransac_filter
from motion_estimator import estimate_motion   # (E, R, t) 구하는 함수
from depth_from_triangulation import triangulate_depths

# ===== 파라미터 =====
MIN_TRACKS      = 60
REFRESH_EVERY   = 25
DISPLAY_SCALE   = 0.8
CALIB_PATH      = "../data/camera_intrinsics.npy"
SCALE_FACTOR    = 0.3     # t 스케일(시각화/누적 안정화)
REVERSE_T       = True    # t 방향 반전 여부 (영상에 따라 조정)
ANCHOR_RADIUS   = 30      # 클릭 지점 주변 반경(픽셀) — 이내 인라이어로 z 추정
Z_SMOOTH_EMA    = 0.3     # 앵커 z 보정(EMA) 계수 (0~1, 높을수록 최신값 반영 큼)
Z_CLIP          = (0.05, 50.0)

# --- 전역 상태 ---
anchor_points = []  # dict: { 'pix':(x,y), 'z':float }
K_global = None
R_total = np.eye(3, dtype=np.float32)
t_total = np.zeros((3,1), dtype=np.float32)

# 최근 매칭/포즈 — 클릭 시 z 계산에 사용
last_inlier_old = None   # (N,2) 이전 프레임 인라이어
last_inlier_new = None   # (N,2) 현재 프레임 인라이어
last_R = None
last_t = None


def mouse_click(event, x_disp, y_disp, flags, param):
    global anchor_points, last_inlier_old, last_inlier_new, last_R, last_t, K_global

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    if K_global is None or last_inlier_old is None or last_inlier_new is None or last_R is None or last_t is None:
        # 포즈/인라이어 없으면 임시 z=1.0
        x = int(x_disp / DISPLAY_SCALE); y = int(y_disp / DISPLAY_SCALE)
        anchor_points.append({'pix': (x,y), 'z': 1.0})
        print(f"📍 z≈1.000")
        return

    # 1) 창 좌표 → 원본 영상 좌표
    x = int(x_disp / DISPLAY_SCALE)
    y = int(y_disp / DISPLAY_SCALE)

    # 2) 클릭 주변 인라이어만 선택
    pts_old = last_inlier_old.reshape(-1,2)
    d2 = np.sum((pts_old - np.array([x,y], dtype=np.float32))**2, axis=1)
    mask_near = d2 < (ANCHOR_RADIUS**2)
    sel_prev = pts_old[mask_near]
    sel_next = last_inlier_new.reshape(-1,2)[mask_near]

    z_est = 1.0
    if len(sel_prev) >= 8:   # 충분한 대응점일 때만 삼각측량
        depths, _ = triangulate_depths(sel_prev, sel_next, K_global, last_R, last_t)
        if np.isfinite(depths).any():
            # 주변점 깊이의 중앙값 사용 (이상치에 강함)
            z_med = float(np.nanmedian(depths))
            if np.isfinite(z_med):
                z_est = float(np.clip(z_med, *Z_CLIP))

    anchor_points.append({'pix': (x,y), 'z': z_est})
    print(f"📍 z≈{z_est:.3f}")


def project_point(world_point, R, t, K, frame_shape):
    """3D 점을 현재 카메라 프레임으로 투영"""
    h, w = frame_shape[:2]
    cam_point = R @ world_point + t
    if cam_point[2,0] <= 1e-6:
        return None
    proj = K @ cam_point
    proj /= proj[2,0]
    px, py = int(proj[0,0]), int(proj[1,0])
    if 0 <= px < w and 0 <= py < h:
        return px, py
    return None


def main():
    global K_global, R_total, t_total, last_inlier_old, last_inlier_new, last_R, last_t

    video = load_video("../data/3.mp4")
    K_global = np.load(CALIB_PATH) if os.path.exists(CALIB_PATH) else None
    use_pose = K_global is not None

    win = "Pose & Anchor (Triangulated Z)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win, mouse_click)

    ret, prev_frame = video.read()
    if not ret:
        return

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_pts  = extract_features(prev_gray)
    frame_idx = 0

    while True:
        ret, frame = video.read()
        if not ret: break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if REFRESH_EVERY and frame_idx>0 and frame_idx % REFRESH_EVERY == 0:
            prev_pts = extract_features(prev_gray)

        if prev_pts is not None and len(prev_pts) > 0:
            next_pts, status, err = cv2.calcOpticalFlowPyrLK(
                prev_gray, gray, prev_pts, None,
                winSize=(21,21), maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
            )
            if next_pts is not None and status is not None:
                good_new = next_pts[status.flatten()==1]
                good_old = prev_pts[status.flatten()==1]

                if len(good_new) >= MIN_TRACKS:
                    inlier_prev, inlier_next, mask_r, _ = ransac_filter(good_old, good_new)

                    if use_pose and len(inlier_prev) >= 8:
                        # Essential + Pose
                        R, t, _ = estimate_motion(inlier_prev, inlier_next, K_global)
                        if R is not None and t is not None:
                            # 누적 포즈 (간단한 합성)
                            R_total = R @ R_total
                            step = (R_total @ (t * SCALE_FACTOR))
                            t_total = t_total - step if REVERSE_T else t_total + step

                            # 🔸 클릭시 사용할 "최근 포즈/인라이어" 갱신
                            last_inlier_old = inlier_prev.astype(np.float32).copy()
                            last_inlier_new = inlier_next.astype(np.float32).copy()
                            last_R, last_t  = R.copy(), t.copy()

        # --- 앵커를 현재 프레임에 투영 ---
        if use_pose and len(anchor_points) > 0:
            for a in anchor_points:
                x, y = a['pix']
                z    = a['z']
                # 픽셀→정규화→3D (이전 좌표계 기준)
                pix = np.array([[x],[y],[1.0]], dtype=np.float32)
                ray = np.linalg.inv(K_global).astype(np.float32) @ pix
                world_prev = ray * z  # 이전 프레임 좌표계 3D

                # 누적 포즈(R_total, t_total)는 "현재" 카메라의 이전 좌표계에 대한 포즈
                proj = project_point(world_prev, R_total, t_total, K_global, frame.shape)
                if proj is not None:
                    px, py = proj
                    cv2.circle(frame, (px,py), 8, (0,255,0), -1)

        disp = cv2.resize(frame, (int(frame.shape[1]*DISPLAY_SCALE), int(frame.shape[0]*DISPLAY_SCALE)))
        cv2.imshow(win, disp)
        if cv2.waitKey(20) & 0xFF == ord('q'):
            break

        prev_gray = gray.copy()
        prev_pts  = next_pts if 'next_pts' in locals() and next_pts is not None else extract_features(gray)
        frame_idx += 1

    video.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
