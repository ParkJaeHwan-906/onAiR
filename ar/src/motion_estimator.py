import cv2
import numpy as np

def estimate_motion(good_prev, good_next, K):
    """
    Essential Matrix 기반의 카메라 회전(R), 이동(t) 추정
    Parameters:
        good_prev : np.ndarray
            이전 프레임의 inlier 특징점
        good_next : np.ndarray
            현재 프레임의 inlier 특징점
        K : np.ndarray (3x3)
            카메라 내부 파라미터 행렬 (fx, fy, cx, cy)
    Returns:
        R : np.ndarray (3x3)
            회전 행렬
        t : np.ndarray (3x1)
            이동 벡터
        mask_pose : np.ndarray
            RANSAC 기반의 inlier mask
    """
    if len(good_prev) < 8 or len(good_next) < 8:
        # Essential Matrix 계산 최소 조건: 대응점 8쌍 이상
        return np.eye(3), np.zeros((3, 1)), None

    E, mask = cv2.findEssentialMat(
        good_next, good_prev, K,
        method=cv2.RANSAC, prob=0.999, threshold=1.0
    )

    if E is None or mask is None:
        # 계산 실패 시 기본값 반환
        return np.eye(3), np.zeros((3, 1)), None

    # E에서 R(회전), t(이동) 복원
    _, R, t, mask_pose = cv2.recoverPose(E, good_next, good_prev, K)
    return R, t, mask_pose
