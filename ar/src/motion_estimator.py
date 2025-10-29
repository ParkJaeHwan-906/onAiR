import cv2
import numpy as np

def estimate_motion_ransac(good_prev, good_next, K, threshold=1.0, prob=0.999):
    """
    RANSAC 기반으로 Essential Matrix를 계산하고
    카메라의 회전(R)과 이동(t)을 추정합니다.

    Parameters
    ----------
    good_prev : np.ndarray
        이전 프레임의 특징점 좌표 (Nx2)
    good_next : np.ndarray
        현재 프레임의 특징점 좌표 (Nx2)
    K : np.ndarray (3x3)
        카메라 내부 파라미터 행렬
    threshold : float
        인라이어 판정 기준 (픽셀 단위)
    prob : float
        RANSAC 신뢰도 (기본 0.999)

    Returns
    -------
    R : np.ndarray (3x3)
        회전 행렬
    t : np.ndarray (3x1)
        이동 벡터
    inlier_mask : np.ndarray
        인라이어 마스크 (1: inlier, 0: outlier)
    E : np.ndarray
        Essential Matrix
    """
    if len(good_prev) < 8 or len(good_next) < 8:
        print("⚠️ RANSAC: 대응점 부족 (< 8)")
        return np.eye(3), np.zeros((3, 1)), None, None

    # ✅ 1. Essential Matrix 계산 + RANSAC 적용
    E, mask = cv2.findEssentialMat(
        good_next, good_prev, K,
        method=cv2.RANSAC,
        prob=prob,
        threshold=threshold
        # ,maxIters=10000
    )

    if E is None or mask is None:
        print("❌ Essential Matrix 계산 실패")
        return np.eye(3), np.zeros((3, 1)), None, None

    # ✅ 2. 인라이어만 남기기
    inlier_mask = mask.ravel().astype(bool)
    good_prev_in = good_prev[inlier_mask]
    good_next_in = good_next[inlier_mask]

    # ✅ 3. Pose 복원 (R, t)
    _, R, t, mask_pose = cv2.recoverPose(E, good_next_in, good_prev_in, K)

    return R, t, inlier_mask, E