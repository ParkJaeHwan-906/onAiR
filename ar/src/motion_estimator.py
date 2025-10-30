# 📄 motion_estimator.py
import cv2
import numpy as np


def refine_inliers(good_prev, good_next, E, K):
    """
    Essential Matrix 계산 이후 추가적으로 이상치를 제거하는 단계.
    - Optical Flow 방향 일관성
    - 이동 크기(속도) 통계적 필터링
    - Reprojection Error 기반 정제
    """
    if len(good_prev) < 8:
        return good_prev, good_next

    # ---- (1) Optical Flow 방향 필터 ----
    good_prev = good_prev.reshape(-1, 2)
    good_next = good_next.reshape(-1, 2)
    flow_vecs = good_next - good_prev
    norms = np.linalg.norm(flow_vecs, axis=1, keepdims=True)
    unit_vecs = flow_vecs / (norms + 1e-6)

    mean_dir = np.mean(unit_vecs, axis=0)
    mean_dir /= np.linalg.norm(mean_dir) + 1e-6

    cos_sim = np.dot(unit_vecs, mean_dir)
    direction_mask = cos_sim > 0.7  # 평균 방향과 45° 이내만 유지

    good_prev = good_prev[direction_mask]
    good_next = good_next[direction_mask]
    flow_vecs = flow_vecs[direction_mask]

    # ---- (2) Flow 크기 기반 필터 ----
    if len(flow_vecs) > 5:
        mag = np.linalg.norm(flow_vecs, axis=1)
        mean_mag, std_mag = np.mean(mag), np.std(mag)
        mag_mask = np.abs(mag - mean_mag) < 1.5 * std_mag
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

        good_prev = good_prev[reproj_mask]
        good_next = good_next[reproj_mask]

    return good_prev, good_next


def estimate_motion(good_prev, good_next, K, threshold=1.0, prob=0.999):
    """
    ✅ Essential Matrix 기반 카메라 이동(R, t) 추정
       - 이미 RANSAC 필터를 거친 점들을 입력받음
       - Pose 추정 및 이상치 재정제 수행

    Parameters
    ----------
    good_prev : np.ndarray (Nx2)
        이전 프레임 인라이어 점
    good_next : np.ndarray (Nx2)
        현재 프레임 인라이어 점
    K : np.ndarray (3x3)
        카메라 내부 파라미터 행렬
    threshold : float
        RANSAC 임계값 (기본 1.0)
    prob : float
        신뢰도 (기본 0.999)

    Returns
    -------
    R : np.ndarray (3x3)
        카메라 회전 행렬
    t : np.ndarray (3x1)
        카메라 이동 벡터
    E : np.ndarray (3x3)
        Essential Matrix
    """
    if K is None:
        raise ValueError("❌ 카메라 내부 파라미터 K가 필요합니다.")

    if len(good_prev) < 8 or len(good_next) < 8:
        print("⚠️ 입력점 부족 (< 8)")
        return np.eye(3), np.zeros((3, 1)), None

    # ✅ 1. Essential Matrix 계산
    E, mask = cv2.findEssentialMat(
        good_next, good_prev, K,
        method=cv2.RANSAC,
        prob=prob,
        threshold=threshold
    )

    if E is None or mask is None:
        print("❌ Essential Matrix 계산 실패")
        return np.eye(3), np.zeros((3, 1)), None

    # ✅ 2. Pose 복원 (R, t)
    _, R, t, pose_mask = cv2.recoverPose(E, good_next, good_prev, K)
    print(f"🧭 Pose 추정 완료: t = {np.round(t.flatten(), 4)}")

    # ✅ 3. 추가 정제 (옵션)
    good_prev_ref, good_next_ref = refine_inliers(good_prev, good_next, E, K)
    print(f"🔍 인라이어 {len(good_prev)} → 정제 후 {len(good_prev_ref)}")

    return R, t, E
