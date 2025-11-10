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
MIN_FEATURES = 50
MIN_DIST_BETWEEN = 10.0
MAX_AGE = 30

K_PATH = "../data/K.npy"
if os.path.exists(K_PATH):
    K = np.load(K_PATH)
else:
    fx, fy, cx, cy = 800, 800, 320, 240
    K = np.array([[fx, 0, cx],
                  [0, fy, cy],
                  [0, 0, 1]], dtype=np.float32)


# ==========================================================
# 🎬 메인 (시각화 제거 버전)
# ==========================================================
def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("❌ 비디오를 열 수 없습니다.")
        return

    print("🎬 Optical Flow + Essential Matrix (no visualization)")

    prev_gray = None
    frame_idx = 0

    # ✅ 누적 Pose
    R_total = np.eye(3, dtype=np.float32)
    t_total = np.zeros((3, 1), dtype=np.float32)
    trajectory = []

    feature_pool = {
        "pts": np.empty((0, 1, 2), dtype=np.float32),
        "age": np.empty((0,), dtype=np.int32)
    }

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev_gray is None:
            init_pts, method = extract_features(gray)
            feature_pool["pts"] = init_pts
            feature_pool["age"] = np.zeros(len(init_pts), dtype=np.int32)
            print(f"[{frame_idx:04d}] {method}: {len(init_pts)} initial points")
            prev_gray = gray.copy()
            frame_idx += 1
            continue

        prev_pts = feature_pool["pts"]

        # === Optical Flow ===
        prev_valid, next_valid, _ = track_features(
            prev_gray, gray, prev_pts,
            fb_thresh=1.5,
            large_motion_px=100.0,
            enable_equalize=False,
            blur_var_thresh=12.0,
            lk_win_size=(25, 25),
            lk_max_level=4,
            frame=frame
        )

        # === 점 관리 ===
        if len(next_valid) > 0:
            feature_pool["pts"] = next_valid
            feature_pool["age"] = np.zeros(len(next_valid), dtype=np.int32)
        else:
            feature_pool["age"] += 1

        valid_mask = feature_pool["age"] < MAX_AGE
        feature_pool["pts"] = feature_pool["pts"][valid_mask]
        feature_pool["age"] = feature_pool["age"][valid_mask]

        if len(feature_pool["pts"]) < MIN_FEATURES:
            new_pts, _ = extract_features(gray)
            if new_pts is not None and len(new_pts) > 0:
                if len(feature_pool["pts"]) > 0:
                    dist = np.linalg.norm(
                        new_pts.reshape(-1, 1, 2) - feature_pool["pts"].reshape(1, -1, 2),
                        axis=2
                    )
                    mask_far = (dist.min(axis=1) > MIN_DIST_BETWEEN)
                    added_pts = new_pts[mask_far]
                else:
                    added_pts = new_pts

                if len(added_pts) > 0:
                    feature_pool["pts"] = np.vstack((feature_pool["pts"], added_pts))
                    ages = np.full(len(added_pts), -MAX_AGE, dtype=np.int32)
                    feature_pool["age"] = np.concatenate((feature_pool["age"], ages))
                    print(f"[{frame_idx:04d}] Added {len(added_pts)} points")
            else:
                print(f"[{frame_idx:04d}] ⚠️ Unable to add new features")

        # === RANSAC ===
        if len(prev_valid) >= 8 and len(next_valid) >= 8:
            inlier_prev, inlier_next, F, inlier_mask = ransac_filter(
                prev_valid, next_valid, threshold=1.0, prob=0.999, visualize=False
            )

            if inlier_mask is not None:
                inlier_count = np.count_nonzero(inlier_mask)
                print(f"[{frame_idx:04d}] RANSAC inliers: {inlier_count}/{len(inlier_mask)}")

                # === Essential Matrix 기반 모션 추정 ===
                R, t, E, stats = estimate_motion(inlier_prev, inlier_next, K)
                if stats["pose_ok"]:
                    s = stats["scale"]
                    t_total += R_total @ (s * t)
                    R_total = R @ R_total
                    xyz = t_total.reshape(3)
                    trajectory.append(xyz.copy())

                    print(f"    → pose_ok | xyz=({xyz[0]:.3f}, {xyz[1]:.3f}, {xyz[2]:.3f}) "
                          f"| scale={s:.3f} | inliers={inlier_count}")
                else:
                    print("    → pose failed (low parallax or cheirality)")
        else:
            print(f"[{frame_idx:04d}] Not enough points for RANSAC")

        prev_gray = gray.copy()
        frame_idx += 1

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("✅ Completed: Essential Matrix motion estimation (no visualization)")


# ==========================================================
if __name__ == "__main__":
    main()
