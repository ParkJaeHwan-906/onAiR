import cv2
import numpy as np

def track_features(prev_gray, cur_gray, prev_pts, max_err=20.0, max_move=50.0):
    """
    Lucas–Kanade Optical Flow로 이전 프레임의 특징점 추적
    개선 버전 (오류 처리 + 이상치 필터링 포함)

    Parameters:
        prev_gray : np.ndarray
            이전 프레임 (grayscale)
        cur_gray : np.ndarray
            현재 프레임 (grayscale)
        prev_pts : np.ndarray (N, 1, 2)
            이전 프레임의 특징점 좌표
        max_err : float
            추적 에러 허용 한계 (값이 클수록 관대함)
        max_move : float
            프레임 간 최대 이동 거리 (이상치 제거용)
    Returns:
        good_prev : np.ndarray
            Optical Flow가 성공한 이전 프레임의 점
        good_next : np.ndarray
            Optical Flow가 성공한 현재 프레임의 점
        status : np.ndarray
            각 점의 추적 성공 여부 (1: 성공, 0: 실패)
    """

    # 1️⃣ 입력 검증
    if prev_pts is None or len(prev_pts) == 0:
        print("[WARN] track_features: 입력 특징점이 없습니다.")
        return np.array([]), np.array([]), np.array([])

    # 2️⃣ Optical Flow 계산
    next_pts, status, err = cv2.calcOpticalFlowPyrLK(
        prev_gray, cur_gray, prev_pts, None,
        winSize=(21, 21),           # 추적 영역 윈도우 크기
        maxLevel=3,                 # 피라미드 레벨 (멀리 이동한 점도 추적)
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
    )

    if next_pts is None or status is None or err is None:
        print("[WARN] track_features: Optical Flow 계산 실패")
        return np.array([]), np.array([]), np.array([])

    # 3️⃣ 성공한 점만 필터링
    good_prev = prev_pts[status.flatten() == 1]
    good_next = next_pts[status.flatten() == 1]
    err_good = err[status.flatten() == 1]

    # 4️⃣ 에러 기반 필터링 (너무 큰 에러 제거)
    mask_err = err_good.flatten() < max_err
    good_prev = good_prev[mask_err]
    good_next = good_next[mask_err]

    # 5️⃣ 이동 거리 기반 이상치 제거 (움직임이 너무 큰 점 제외)
    move_dist = np.linalg.norm(good_next - good_prev, axis=1)
    mask_move = move_dist < max_move
    good_prev = good_prev[mask_move]
    good_next = good_next[mask_move]

    # 6️⃣ 최소 유효점 검사
    if len(good_prev) < 5:
        print(f"[WARN] track_features: 유효한 추적점이 너무 적습니다. ({len(good_prev)}개)")
        return np.array([]), np.array([]), np.array([])

    return good_prev, good_next, status
