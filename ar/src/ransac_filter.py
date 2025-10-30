# 📄 ransac_filter.py
import cv2
import numpy as np

def ransac_filter(good_prev, good_next, method="fundamental", threshold=1.0, prob=0.999):
    """
    ✅ Optical Flow 대응점 쌍에서 RANSAC을 이용해 이상치(outlier) 제거만 수행.
    (Essential Matrix 계산이나 Pose 추정은 하지 않음)

    Parameters
    ----------
    good_prev : np.ndarray
        이전 프레임의 특징점 좌표 (Nx2)
    good_next : np.ndarray
        현재 프레임의 특징점 좌표 (Nx2)
    method : str
        'fundamental' (기본값) 또는 'homography'
    threshold : float
        인라이어 판정 기준 (픽셀 단위)
    prob : float
        RANSAC 신뢰도 (기본값 0.999)

    Returns
    -------
    inlier_prev : np.ndarray
        인라이어로 판정된 이전 프레임 점
    inlier_next : np.ndarray
        인라이어로 판정된 현재 프레임 점
    mask : np.ndarray
        RANSAC 인라이어 마스크 (1=inlier, 0=outlier)
    model : np.ndarray
        추정된 모델 행렬 (Fundamental 또는 Homography)
    """

    if len(good_prev) < 8 or len(good_next) < 8:
        print("⚠️ RANSAC: 대응점 부족 (< 8)")
        return np.array([]), np.array([]), None, None

    if method == "fundamental":
        model, mask = cv2.findFundamentalMat(
            good_prev, good_next,
            method=cv2.FM_RANSAC,
            ransacReprojThreshold=threshold,
            confidence=prob
        )
    elif method == "homography":
        model, mask = cv2.findHomography(
            good_prev, good_next,
            method=cv2.RANSAC,
            ransacReprojThreshold=threshold,
            confidence=prob
        )
    else:
        raise ValueError("❌ method는 'fundamental' 또는 'homography' 중 하나여야 합니다.")

    if model is None or mask is None:
        print("❌ RANSAC 모델 추정 실패")
        return np.array([]), np.array([]), None, None

    # 인라이어만 필터링
    mask = mask.ravel().astype(bool)
    inlier_prev = good_prev[mask]
    inlier_next = good_next[mask]

    print(f"🧩 RANSAC 인라이어: {len(inlier_prev)}/{len(good_prev)}")

    return inlier_prev, inlier_next, mask, model
