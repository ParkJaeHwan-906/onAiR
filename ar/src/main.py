import cv2
import numpy as np
import os

from feature_extractor import extract_features
from feature_tracker import track_features
from ransac_filter import ransac_filter
from motion_estimator import estimate_motion


# ==========================================================
# 🎯 설정
# ==========================================================
VIDEO_PATH = "../data/7.mp4"
INTR_PATH = "../data/camera_intrinsics.npy"
DIST_PATH = "../data/dist_coeffs.npy"

os.makedirs("output/features", exist_ok=True)
os.makedirs("output/flow", exist_ok=True)
os.makedirs("output/ransac", exist_ok=True)
os.makedirs("output/motion", exist_ok=True)


# ==========================================================
# 🔧 카메라 파라미터 로드
# ==========================================================
def load_camera_params():
    if os.path.exists(INTR_PATH):
        K = np.load(INTR_PATH)
        print("📌 Loaded K from camera_intrinsics.npy")
    else:
        print("⚠️ camera_intrinsics.npy 없음 → 기본 K 사용")
        K = np.array([[800, 0, 320],
                      [0, 800, 240],
                      [0, 0,   1]], dtype=np.float32)

    if os.path.exists(DIST_PATH):
        D = np.load(DIST_PATH)
        print("📌 Loaded distortion coeffs from dist_coeffs.npy")
    else:
        print("⚠️ dist_coeffs.npy 없음 → 왜곡 보정 없이 진행")
        D = None

    return K, D


# ==========================================================
# 🔧 특징점 시각화 (강조)
# ==========================================================
def save_feature_frame(frame, pts, method, frame_idx):
    vis = frame.copy()

    if pts is None:
        pts = np.empty((0, 1, 2))

    for (x, y) in pts.reshape(-1, 2):
        cv2.circle(vis, (int(x), int(y)), 5, (0, 255, 0), -1)
        cv2.circle(vis, (int(x), int(y)), 9, (0, 255, 0), 2)

    overlay = vis.copy()
    cv2.rectangle(overlay, (10, 10), (420, 70), (0, 0, 0), -1)
    vis = cv2.addWeighted(overlay, 0.4, vis, 0.6, 0)

    cv2.putText(vis,
                f"{method if method else 'feat'} | {len(pts)} pts",
                (20, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.4,
                (0, 255, 255),
                3)

    cv2.imwrite(f"output/features/frame_{frame_idx:04d}.jpg", vis)


# ==========================================================
# 🔧 Optical Flow 시각화 (강조)
# ==========================================================
def save_optical_flow_frame(frame, prev_pts, next_pts, frame_idx, flow_scale=10):
    vis = frame.copy()

    if prev_pts is None:
        prev_pts = np.empty((0, 1, 2))
    if next_pts is None:
        next_pts = np.empty((0, 1, 2))

    for p1, p2 in zip(prev_pts, next_pts):
        x1, y1 = p1[0]
        x2, y2 = p2[0]

        dx = (x2 - x1)
        dy = (y2 - y1)

        ex = int(x1 + dx * flow_scale)
        ey = int(y1 + dy * flow_scale)

        cv2.arrowedLine(vis, (int(x1), int(y1)), (ex, ey),
                        (0, 0, 255), 4, tipLength=0.3)

        cv2.circle(vis, (int(x1), int(y1)), 5, (0, 255, 255), -1)

    overlay = vis.copy()
    cv2.rectangle(overlay, (10, 10), (350, 70), (0, 0, 0), -1)
    vis = cv2.addWeighted(overlay, 0.5, vis, 0.5, 0)

    cv2.putText(vis, f"Optical Flow: {len(prev_pts)} pts",
                (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.4,
                (0, 255, 255), 3)

    cv2.imwrite(f"output/flow/flow_{frame_idx:04d}.jpg", vis)


# ==========================================================
# 🔧 RANSAC 시각화 (강조: Inlier 화살표 / Outlier X)
# ==========================================================
def save_ransac_frame(frame, prev_pts, next_pts, mask, frame_idx, flow_scale=10):
    vis = frame.copy()

    if prev_pts is None:
        prev_pts = np.empty((0, 1, 2))
    if next_pts is None:
        next_pts = np.empty((0, 1, 2))
    if mask is None:
        mask = np.zeros((len(prev_pts),))

    mask = mask.astype(bool)

    for (p1, p2, m) in zip(prev_pts, next_pts, mask):
        x1, y1 = p1[0]
        x2, y2 = p2[0]
        dx = (x2 - x1)
        dy = (y2 - y1)

        ex = int(x1 + dx * flow_scale)
        ey = int(y1 + dy * flow_scale)

        if m:  # inlier
            cv2.arrowedLine(vis, (int(x1), int(y1)), (ex, ey),
                            (0, 255, 0), 5, tipLength=0.3)
            cv2.circle(vis, (int(x1), int(y1)), 6, (0, 255, 255), -1)
        else:  # outlier
            size = 10
            cv2.line(vis, (int(x1-size), int(y1-size)),
                     (int(x1+size), int(y1+size)), (0, 0, 255), 4)
            cv2.line(vis, (int(x1-size), int(y1+size)),
                     (int(x1+size), int(y1-size)), (0, 0, 255), 4)

    inliers = np.sum(mask)
    total = len(mask)

    overlay = vis.copy()
    cv2.rectangle(overlay, (10, 10), (520, 70), (0, 0, 0), -1)
    vis = cv2.addWeighted(overlay, 0.5, vis, 0.5, 0)

    cv2.putText(vis,
                f"RANSAC Inliers {inliers}/{total} ({(inliers/total*100 if total>0 else 0):.1f}%)",
                (20, 55), cv2.FONT_HERSHEY_SIMPLEX,
                1.4, (0, 255, 255), 3)

    cv2.imwrite(f"output/ransac/ransac_{frame_idx:04d}.jpg", vis)


# ==========================================================
# 🔧 Motion 시각화 (scale 강조)
# ==========================================================
def save_motion_frame(frame, scale, frame_idx):
    vis = frame.copy()

    overlay = vis.copy()
    cv2.rectangle(overlay, (10, 10), (350, 70), (0, 0, 0), -1)
    vis = cv2.addWeighted(overlay, 0.4, vis, 0.6, 0)

    color = (0, 220, 255) if scale > 0 else (255, 150, 150)

    cv2.putText(vis,
                f"Scale(Z): {scale:.4f}",
                (20, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.6,
                color,
                3)

    cv2.imwrite(f"output/motion/motion_{frame_idx:04d}.jpg", vis)


# ==========================================================
# 🎬 메인 Pipeline
# ==========================================================
def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("❌ Video open 실패")
        return

    K, D = load_camera_params()

    frame_idx = 0
    prev_gray = None
    prev_pts = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_undist = frame  # undistort 끔
        gray = cv2.cvtColor(frame_undist, cv2.COLOR_BGR2GRAY)

        # 첫 프레임: 특징점
        if prev_gray is None:
            prev_pts, method = extract_features(gray)
            save_feature_frame(frame_undist, prev_pts, method, frame_idx)
            prev_gray = gray
            frame_idx += 1
            continue

        # Optical Flow
        prev_valid, next_valid, _ = track_features(
            prev_gray, gray, prev_pts,
            fb_thresh=2.0, blur_var_thresh=12.0,
            lk_win_size=(25, 25), lk_max_level=4,
            frame=frame_undist
        )

        if prev_valid is None:
            prev_valid = np.empty((0, 1, 2))
        if next_valid is None:
            next_valid = np.empty((0, 1, 2))

        save_optical_flow_frame(frame_undist, prev_valid, next_valid, frame_idx)

        # RANSAC
        if len(prev_valid) >= 8:
            in_prev, in_next, F, mask = ransac_filter(
                prev_valid, next_valid,
                threshold=1.0, prob=0.999,
                frame_shape=frame_undist.shape,
                grid_size=(8, 6),
                dir_cos_thresh=0.5,
                sigma_scale=2.0
            )
        else:
            in_prev = prev_valid
            in_next = next_valid
            mask = np.zeros((len(prev_valid),))

        save_ransac_frame(frame_undist, prev_valid, next_valid, mask, frame_idx)

        # Motion Scale
        scale = -1.0
        if len(in_prev) >= 8:
            R, t, scale_est, stats = estimate_motion(in_prev, in_next, K)
            if stats.get("pose_ok", False):
                scale = scale_est

        save_motion_frame(frame_undist, scale, frame_idx)

        # 다음 프레임 특징점 (재추출)
        curr_pts, method = extract_features(gray)
        save_feature_frame(frame_undist, curr_pts, method, frame_idx)

        prev_gray = gray
        prev_pts = curr_pts
        frame_idx += 1

    cap.release()
    print("✨ DONE → output/{features,flow,ransac,motion}")


if __name__ == "__main__":
    main()
