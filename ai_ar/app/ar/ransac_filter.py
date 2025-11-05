import cv2
import numpy as np

def ransac_filter(
    good_prev, good_next,
    K=None, distCoeffs=None,
    threshold=1.0,
    prob=0.999,
    auto_model=True,
    visualize=False,
    frame=None
):
    """
    Optical Flow 대응점 기반 RANSAC 필터링 (개선 버전)
    - Fundamental/Homography 자동 선택
    - 보정된 좌표 기반 옵션 추가
    - 인라이어 비율 동적 조정
    """

    # 1️⃣ 입력 유효성 검사
    if good_prev is None or good_next is None:
        print("⚠️ 입력이 None 입니다.")
        return np.array([]), np.array([]), None, None
    if len(good_prev) < 8 or len(good_next) < 8:
        print(f"⚠️ RANSAC: 대응점 부족 ({len(good_prev)}개)")
        return np.array([]), np.array([]), None, None

    # 2️⃣ 좌표 형상 통일
    good_prev = np.squeeze(good_prev)
    good_next = np.squeeze(good_next)

    # 3️⃣ 보정된 좌표 변환 (필요할 때만)
    if K is not None:
        good_prev_norm = cv2.undistortPoints(good_prev, K, distCoeffs)
        good_next_norm = cv2.undistortPoints(good_next, K, distCoeffs)
    else:
        good_prev_norm = good_prev
        good_next_norm = good_next

    # 4️⃣ 모델 후보 계산
    F, maskF = cv2.findFundamentalMat(
        good_prev_norm, good_next_norm,
        method=cv2.FM_RANSAC,
        ransacReprojThreshold=threshold,
        confidence=prob
    )
    H, maskH = cv2.findHomography(
        good_prev_norm, good_next_norm,
        method=cv2.RANSAC,
        ransacReprojThreshold=threshold * 2.0,  # Homography는 조금 관대하게
        confidence=prob
    )

    # 5️⃣ 자동 모델 선택
    chosen_model, mask = None, None
    if auto_model and maskF is not None and maskH is not None:
        inlier_ratio_F = np.count_nonzero(maskF) / len(maskF)
        inlier_ratio_H = np.count_nonzero(maskH) / len(maskH)
        if inlier_ratio_H > 0.8:   # 평면씬일 가능성 높음
            chosen_model, mask, model_type = H, maskH, "Homography"
        else:
            chosen_model, mask, model_type = F, maskF, "Fundamental"
    else:
        chosen_model, mask, model_type = F, maskF, "Fundamental"

    # 6️⃣ 재시도 (인라이어 너무 적으면 threshold 완화)
    if mask is None or np.count_nonzero(mask) < 8:
        threshold *= 1.5
        F, maskF = cv2.findFundamentalMat(
            good_prev_norm, good_next_norm,
            method=cv2.FM_RANSAC,
            ransacReprojThreshold=threshold,
            confidence=prob
        )
        chosen_model, mask, model_type = F, maskF, "Fundamental"

    if mask is None:
        print("❌ RANSAC 모델 추정 실패")
        return np.array([]), np.array([]), None, None

    # 7️⃣ 인라이어 추출
    mask = mask.ravel().astype(bool)
    inlier_prev = good_prev[mask]
    inlier_next = good_next[mask]

    # 8️⃣ 시각화 (디버깅용)
    if visualize and frame is not None:
        vis = frame.copy()
        for (p1, p2, m) in zip(good_prev, good_next, mask):
            c = (0, 255, 0) if m else (0, 0, 255)
            cv2.line(vis, tuple(p1.astype(int)), tuple(p2.astype(int)), c, 1)
            cv2.circle(vis, tuple(p2.astype(int)), 2, c, -1)
        cv2.imshow("RANSAC Inliers", vis)
        cv2.waitKey(1)

    inlier_ratio = np.count_nonzero(mask) / len(mask)
    # print(f"🧩 [{model_type}] 인라이어 비율: {inlier_ratio*100:.1f}%")

    return inlier_prev, inlier_next, mask, chosen_model
