import cv2
import numpy as np
import os

from feature_extractor import extract_features
from feature_tracker import track_features
from ransac_filter import ransac_filter


# ==========================================================
# 🎯 설정
# ==========================================================
VIDEO_PATH = "../data/test.mp4"
INTR_PATH = "../data/camera_intrinsics.npy"
DIST_PATH = "../data/dist_coeffs.npy"

os.makedirs("output/features", exist_ok=True)
os.makedirs("output/flow", exist_ok=True)
os.makedirs("output/ransac", exist_ok=True)


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

    # optical flow count
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
        color = (0, 255, 0) if m else (0, 0, 255)  # green = inlier, red = outlier
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
# 🔧 특징점 저장
# ==========================================================
def save_feature_frame(frame, pts, method, frame_idx):
    vis = frame.copy()

    for (x, y) in pts.reshape(-1, 2):
        cv2.circle(vis, (int(x), int(y)), 1, (0, 255, 0), -1)

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
# 🎬 메인 (FEATURE + OPTICAL FLOW + RANSAC)
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

    print("🎬 Running FEATURE + OPTICAL FLOW + RANSAC debug mode…")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 🔹 undistort
        if D is not None:
            frame_undist = cv2.undistort(frame, K, D)
        else:
            frame_undist = frame

        gray = cv2.cvtColor(frame_undist, cv2.COLOR_BGR2GRAY)

        # ========== 1) 첫 프레임 특징점 ==========
        if prev_gray is None:
            prev_pts, method = extract_features(gray)
            print(f"[{frame_idx:04d}] {method}: {len(prev_pts)} pts (INIT)")
            save_feature_frame(frame_undist, prev_pts, method, frame_idx)
            prev_gray = gray.copy()
            frame_idx += 1
            continue

        # ========== 2) Optical Flow ==========
        prev_valid, next_valid, _ = track_features(
            prev_gray, gray, prev_pts,
            fb_thresh=2.0,
            blur_var_thresh=12.0,
            lk_win_size=(25, 25),
            lk_max_level=4,
            frame=frame_undist
        )

        print(f"[{frame_idx:04d}] Tracked: {len(prev_valid)} pts")

        if len(prev_valid) == 0:
            prev_pts = []
            prev_gray = gray.copy()
            frame_idx += 1
            continue

        save_optical_flow_frame(frame_undist, prev_valid, next_valid, frame_idx)

        # ========== 3) RANSAC 적용 ==========
        in_prev, in_next, F, mask = ransac_filter(
            prev_valid, next_valid,
            threshold=1.0,
            prob=0.999,
            frame_shape=frame.shape,
            grid_size=(8, 6),
            dir_cos_thresh=0.5,
            sigma_scale=2.0
        )

        if mask is None:
            print(f"[{frame_idx:04d}] RANSAC failed")
        else:
            # RANSAC 저장
            save_ransac_frame(frame_undist, prev_valid, next_valid, mask, frame_idx)

            inliers = np.count_nonzero(mask)
            total = len(mask)
            ratio = (inliers / total * 100) if total > 0 else 0
            print(f"[{frame_idx:04d}] RANSAC Inliers: {inliers}/{total} ({ratio:.1f}%)")

        # ========== 4) 특징점 부족하면 재추출 ==========
        if len(in_prev) < 300:
            new_pts, method = extract_features(gray)
            if len(new_pts) > 0:
                prev_pts = np.vstack([in_next, new_pts])
                print(f"[{frame_idx:04d}] Added {len(new_pts)} new pts → total {len(prev_pts)}")
            else:
                prev_pts = in_next
        else:
            prev_pts = in_next

        # ========== 5) 다음 프레임 준비 ==========
        prev_gray = gray.copy()
        frame_idx += 1

    cap.release()
    print("✅ 저장 완료 → output/{features,flow,ransac}/")


# ==========================================================
# 🔧 실행
# ==========================================================
if __name__ == "__main__":
    main()
