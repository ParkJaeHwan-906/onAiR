import cv2
import numpy as np

def refine_inliers(good_prev, good_next, E, K):
    """
    RANSAC 이후 추가적으로 이상치를 제거하는 필터링 단계.
    1️⃣ Optical Flow 방향 일관성
    2️⃣ 이동 크기(속도) 통계적 필터링
    3️⃣ Reprojection Error 기반 정제
    """
    if len(good_prev) < 8:
        return good_prev, good_next

    # ---- (1) Optical Flow 방향 필터 ----
    good_prev = good_prev.reshape(-1, 2)
    good_next = good_next.reshape(-1, 2)
    flow_vecs = good_next - good_prev  # (N, 2)
    norms = np.linalg.norm(flow_vecs, axis=1, keepdims=True)
    unit_vecs = flow_vecs / (norms + 1e-6)

    mean_dir = np.mean(unit_vecs, axis=0)
    mean_dir /= np.linalg.norm(mean_dir) + 1e-6

    cos_sim = np.dot(unit_vecs, mean_dir)
    direction_mask = cos_sim > 0.7  # 배경 방향과 45도 이내인 점만 유지

    good_prev = good_prev[direction_mask]
    good_next = good_next[direction_mask]
    flow_vecs = flow_vecs[direction_mask]

    # ---- (2) Flow 크기 기반 필터 ----
    if len(flow_vecs) > 5:
        mag = np.linalg.norm(flow_vecs, axis=1)  # (N,)
        mean_mag = np.mean(mag)
        std_mag = np.std(mag)
        mag_mask = np.abs(mag - mean_mag) < 1.5 * std_mag  # 속도 이상치 제거
        mag_mask = mag_mask.astype(bool).reshape(-1)       # ✅ 안전하게 flatten
        good_prev = good_prev[mag_mask]
        good_next = good_next[mag_mask]
        flow_vecs = flow_vecs[mag_mask]

    # ---- (3) Reprojection Error 기반 필터 ----
    if len(good_prev) >= 8:
        good_prev_norm = cv2.undistortPoints(good_prev.reshape(-1, 1, 2), K, None)
        good_next_norm = cv2.undistortPoints(good_next.reshape(-1, 1, 2), K, None)

        x1_h = np.hstack([good_prev_norm[:, 0], np.ones((len(good_prev_norm), 1))])
        x2_h = np.hstack([good_next_norm[:, 0], np.ones((len(good_next_norm), 1))])

        err = np.abs(np.sum(x2_h * (E @ x1_h.T).T, axis=1))
        reproj_mask = err < np.percentile(err, 80)

        reproj_mask = reproj_mask.astype(bool).reshape(-1)
        good_prev = good_prev[reproj_mask]
        good_next = good_next[reproj_mask]

    return good_prev, good_next

def estimate_motion_ransac(good_prev, good_next, K, threshold=1.0, prob=0.999):
    """
    RANSAC 기반으로 Essential Matrix를 계산하고
    카메라의 회전(R)과 이동(t)을 추정합니다.
    이후 refine_inliers()로 동적 객체 제거까지 수행합니다.
    """
    if len(good_prev) < 8 or len(good_next) < 8:
        print("⚠️ RANSAC: 대응점 부족 (< 8)")
        return np.eye(3), np.zeros((3, 1)), None, None

    # ✅ 1. Essential Matrix 계산 (RANSAC 기반)
    E, mask = cv2.findEssentialMat(
        good_next, good_prev, K,
        method=cv2.RANSAC,
        prob=prob,
        threshold=threshold
    )

    if E is None or mask is None:
        print("❌ Essential Matrix 계산 실패")
        return np.eye(3), np.zeros((3, 1)), None, None

    # ✅ 2. 인라이어 필터링
    inlier_mask = mask.ravel().astype(bool)
    good_prev_in = good_prev[inlier_mask]
    good_next_in = good_next[inlier_mask]

    if len(good_prev_in) < 8:
        print("⚠️ 인라이어 부족 — Pose 계산 생략")
        return np.eye(3), np.zeros((3, 1)), inlier_mask, E

    # ✅ 3. Pose 복원 (R, t)
    _, R, t, mask_pose = cv2.recoverPose(E, good_next_in, good_prev_in, K)

    # ✅ 4. 추가 정제 단계 (Flow 기반 이상치 제거)
    good_prev_ref, good_next_ref = refine_inliers(good_prev_in, good_next_in, E, K)

    print(f"🔍 RANSAC 후 특징점: {len(good_prev_in)} → 정제 후: {len(good_prev_ref)}")

    return R, t, inlier_mask, E
