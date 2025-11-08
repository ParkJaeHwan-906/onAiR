import cv2
import numpy as np

def ransac_filter(
    good_prev,
    good_next,
    K=None,
    distCoeffs=None,
    threshold=1.0,
    prob=0.999,
    use_motion_filter=True,
    motion_dir_cos=0.5,
    motion_mag_ratio=0.2,
    visualize=False,
    frame=None,
):
    """
    RANSAC 기반 대응점 정제 필터 (Fundamental Matrix + 방향성 일관성 필터 포함)

    Parameters
    ----------
    good_prev, good_next : np.ndarray
        Optical Flow로 추적된 대응점 쌍 (N,1,2) or (N,2)
    K, distCoeffs : np.ndarray or None
        (선택) 카메라 내부 파라미터 (보정용)
    threshold : float
        RANSAC reprojection 허용 오차 (px)
    prob : float
        RANSAC 신뢰도 (0~1)
    use_motion_filter : bool
        True면 카메라 전체 이동 방향 기준으로 물리적 방향성 검증 수행
    motion_dir_cos : float
        방향 유사도 기준 (cosine similarity) — 1.0은 완전 동일
    motion_mag_ratio : float
        평균 이동 크기 대비 최소 비율 (너무 작은 이동 제거)
    visualize : bool
        True일 경우 RANSAC 결과를 시각화 (초록: 인라이어, 빨강: 아웃라이어)
    frame : np.ndarray
        시각화용 원본 프레임 (None 가능)

    Returns
    -------
    inlier_prev, inlier_next : np.ndarray
        정제된 인라이어 점 쌍
    F : np.ndarray
        Fundamental Matrix
    mask : np.ndarray
        인라이어 마스크 (bool)
    """

    # 1️⃣ 입력 유효성 검사
    if good_prev is None or good_next is None:
        return np.array([]), np.array([]), None, None
    if len(good_prev) < 8 or len(good_next) < 8:
        return np.array([]), np.array([]), None, None

    # 좌표 정리 (형상 (N,2))
    good_prev = np.squeeze(good_prev)
    good_next = np.squeeze(good_next)

    # 2️⃣ (선택) 렌즈 왜곡 보정
    if K is not None:
        good_prev_norm = cv2.undistortPoints(good_prev, K, distCoeffs)
        good_next_norm = cv2.undistortPoints(good_next, K, distCoeffs)
    else:
        good_prev_norm = good_prev
        good_next_norm = good_next

    # 3️⃣ Fundamental Matrix 추정 (RANSAC)
    F, mask = cv2.findFundamentalMat(
        good_prev_norm,
        good_next_norm,
        method=cv2.FM_RANSAC,
        ransacReprojThreshold=threshold,
        confidence=prob,
    )

    # 4️⃣ 인라이어 부족 시 재시도 (Adaptive threshold)
    if mask is None or np.count_nonzero(mask) < 8:
        threshold *= 1.5
        F, mask = cv2.findFundamentalMat(
            good_prev_norm,
            good_next_norm,
            method=cv2.FM_RANSAC,
            ransacReprojThreshold=threshold,
            confidence=prob,
        )
    if mask is None:
        print("❌ Fundamental Matrix 추정 실패")
        return np.array([]), np.array([]), None, None

    mask = mask.ravel().astype(bool)
    inlier_prev = good_prev[mask]
    inlier_next = good_next[mask]

    # # 5️⃣ (옵션) 방향성 일관성 필터
    if use_motion_filter and len(inlier_prev) >= 8:
        flow = inlier_next - inlier_prev
        mags = np.linalg.norm(flow, axis=1)
        mean_flow = np.median(flow, axis=0)

        # 방향 유사도 (cosine similarity)
        dot = np.sum(flow * mean_flow, axis=1)
        cos_sim = dot / (np.linalg.norm(flow, axis=1) * np.linalg.norm(mean_flow) + 1e-6)
        mask_dir = cos_sim > motion_dir_cos

        # 이동 크기 비율 필터 (너무 작은 이동 제외)
        mask_mag = mags > (motion_mag_ratio * np.median(mags))

        # 두 조건을 동시에 만족하는 점만 유지
        motion_mask = mask_dir & mask_mag
        inlier_prev = inlier_prev[motion_mask]
        inlier_next = inlier_next[motion_mask]

        # 최종 마스크 업데이트
        mask_final = np.zeros_like(mask, dtype=bool)
        mask_final[np.where(mask)[0][motion_mask]] = True
        mask = mask_final

    return inlier_prev, inlier_next, F, mask






# RANSAC + 백터 잔차 (이동방향 + 거리) 

# 이후 그리드별 잔차를 구해서 신뢰할만한 그리드 특정

# 핑 -> 즉 배경을 추적 (보완)
# -> 모델 ? 프레임 ?
# Optical Flow 랑 비슷하게, 추정치들로 조금 더 정확도를 높일 수 있는 방법 ( 여러 개를 보완하며 개선 )

# 프레임 추적 
# (x, y) -> 픽셀 비교 ? 특징점 ? 
# 완벽하게 ( 거의 ) 일치하는가? 

# Segment AP ? 