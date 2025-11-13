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
VIDEO_PATH = "../data/test.mp4"
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
# 🔧 특징점 저장
# ==========================================================
def save_feature_frame(frame, pts, method, frame_idx):
    vis = frame.copy()

    for (x, y) in pts.reshape(-1, 2):
        cv2.circle(vis, (int(x), int(y)), 2, (0, 255, 0), -1)

    cv2.putText(
        vis,
        f"{method} | {len(pts)} pts",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        2
    )

    cv2.imwrite(f"output/features/frame_{frame_idx:04d}_pts{len(pts)}.jpg", vis)


# ==========================================================
# 🔧 Optical Flow 시각화
# ==========================================================
def save_optical_flow_frame(frame, prev_pts, next_pts, frame_idx):
    vis = frame.copy()

    for p1, p2 in zip(prev_pts, next_pts):
        cv2.arrowedLine(
            vis,
            tuple(p1[0].astype(int)),
            tuple(p2[0].astype(int)),
            (0, 0, 255),
            1,
            tipLength=0.3
        )

    cv2.putText(
        vis,
        f"Tracked: {len(prev_pts)} pts",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        2
    )

    cv2.imwrite(f"output/flow/flow_{frame_idx:04d}.jpg", vis)


# ==========================================================
# 🔧 RANSAC 시각화
# ==========================================================
def save_ransac_frame(frame, prev_pts, next_pts, mask, frame_idx):
    vis = frame.copy()
    mask = mask.astype(bool)

    for (p1, p2, m) in zip(prev_pts, next_pts, mask):
        color = (0, 255, 0) if m else (0, 0, 255)
        cv2.arrowedLine(
            vis,
            tuple(p1[0].astype(int)),
            tuple(p2[0].astype(int)),
            color,
            1,
            tipLength=0.3
        )

    inliers = np.count_nonzero(mask)
    total = len(mask)
    ratio = (inliers / total) * 100 if total > 0 else 0

    cv2.putText(vis, f"Inlier: {inliers}/{total} ({ratio:.1f}%)",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (0, 255, 255), 2)

    cv2.imwrite(f"output/ransac/ransac_{frame_idx:04d}.jpg", vis)


# ==========================================================
# 🔧 Motion Estimator 시각화 (scale)
# ==========================================================
def save_motion_frame(frame, scale, frame_idx):
    vis = frame.copy()
    cv2.putText(vis, f"Scale(Z): {scale:.4f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (255, 200, 0), 2)
    cv2.imwrite(f"output/motion/motion_{frame_idx:04d}.jpg", vis)


# ==========================================================
# 🎬 메인 (FEATURE → FLOW → RANSAC → MOTION)
# ==========================================================
def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("❌ 비디오를 열 수 없습니다.")
        return

    K, D = load_camera_params()

    frame_idx = 0
    prev_gray = None
    prev_pts = None

    print("🎬 Running Full Pipeline (Feature + Flow + RANSAC + Motion)…")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Undistort
        frame_undist = cv2.undistort(frame, K, D) if D is not None else frame
        gray = cv2.cvtColor(frame_undist, cv2.COLOR_BGR2GRAY)

        # ========== 1) 첫 프레임 특징점 ==========
        if prev_gray is None:
            prev_pts, method = extract_features(gray)
            save_feature_frame(frame_undist, prev_pts, method, frame_idx)
            prev_gray = gray.copy()
            frame_idx += 1
            continue

        # ========== 2) Optical Flow ==========
        prev_valid, next_valid, _ = track_features(
            prev_gray,
            gray,
            prev_pts,
            fb_thresh=2.0,
            blur_var_thresh=12.0,
            lk_win_size=(25, 25),
            lk_max_level=4,
            frame=frame_undist
        )

        if len(prev_valid) == 0:
            prev_gray = gray.copy()
            prev_pts = []
            frame_idx += 1
            continue

        save_optical_flow_frame(frame_undist, prev_valid, next_valid, frame_idx)

        # ========== 3) RANSAC ==========
        in_prev, in_next, F, mask = ransac_filter(
            prev_valid, next_valid,
            threshold=1.0,
            prob=0.999,
            frame_shape=frame_undist.shape,
            grid_size=(8, 6),
            dir_cos_thresh=0.5,
            sigma_scale=2.0
        )

        if mask is not None:
            save_ransac_frame(frame_undist, prev_valid, next_valid, mask, frame_idx)
            print(f"[{frame_idx:04d}] RANSAC Inliers = {np.count_nonzero(mask)}/{len(mask)}")

        # ========== 4) Essential-Based Motion (scale for Z) ==========
        R, t, scale, stats = estimate_motion(in_prev, in_next, K)

        if stats["pose_ok"]:
            save_motion_frame(frame_undist, scale, frame_idx)
            print(f"[{frame_idx:04d}] Scale(Z) ≈ {scale:.4f}")

        # ========== 5) 다음 프레임용 포인트 준비 ==========
        # 부족하면 신규 특징점 add
        if len(in_prev) < 300:
            new_pts, method = extract_features(gray)
            if len(new_pts) > 0:
                prev_pts = np.vstack([in_next, new_pts])
            else:
                prev_pts = in_next
        else:
            prev_pts = in_next

        prev_gray = gray.copy()
        frame_idx += 1

    cap.release()
    print("✨ DONE → output/{features, flow, ransac, motion}")


# ==========================================================
# 🔧 실행
# ==========================================================
if __name__ == "__main__":
    main()
