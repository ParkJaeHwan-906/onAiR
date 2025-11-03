# 📄 motion_estimator.py
import cv2
import numpy as np

def _mean_parallax(prev_xy: np.ndarray, next_xy: np.ndarray) -> float:
    return float(np.mean(np.linalg.norm(next_xy - prev_xy, axis=1)))

def refine_inliers(good_prev, good_next, E, K, use_dir_filter=True, drop_top_percent=20):
    """
    Essential Matrix 이후 인라이어 재정제:
    - (옵션) Optical Flow 방향/크기 필터
    - 정규화 좌표 기반 epipolar reprojection 오차 상위 퍼센트 제거
    """
    if good_prev is None or good_next is None:
        return np.array([]), np.array([])
    if len(good_prev) < 8:
        return good_prev, good_next

    prev_xy = good_prev.reshape(-1, 2)
    next_xy = good_next.reshape(-1, 2)

    flow = next_xy - prev_xy
    if use_dir_filter and len(flow) >= 8:
        # 방향 일관성
        unit = flow / (np.linalg.norm(flow, axis=1, keepdims=True) + 1e-6)
        mean_dir = unit.mean(axis=0)
        nd = np.linalg.norm(mean_dir) + 1e-6
        mean_dir /= nd
        cos_sim = unit @ mean_dir
        dir_mask = cos_sim > 0.7
        prev_xy, next_xy, flow = prev_xy[dir_mask], next_xy[dir_mask], flow[dir_mask]

    if len(flow) >= 8:
        # 크기 통계 필터
        mag = np.linalg.norm(flow, axis=1)
        m, s = np.mean(mag), np.std(mag)
        mag_mask = np.abs(mag - m) < 1.5 * (s + 1e-6)
        prev_xy, next_xy = prev_xy[mag_mask], next_xy[mag_mask]

    if len(prev_xy) < 8:
        return prev_xy, next_xy

    # 정규화 좌표에서 epipolar 제약 오차로 재정제
    p1n = cv2.undistortPoints(prev_xy.reshape(-1, 1, 2), K, None)
    p2n = cv2.undistortPoints(next_xy.reshape(-1, 1, 2), K, None)
    x1 = np.hstack([p1n[:, 0], np.ones((len(p1n), 1))])
    x2 = np.hstack([p2n[:, 0], np.ones((len(p2n), 1))])
    err = np.abs(np.sum(x2 * (E @ x1.T).T, axis=1))

    keep = err < np.percentile(err, 100 - drop_top_percent)
    return prev_xy[keep].reshape(-1, 2), next_xy[keep].reshape(-1, 2)

def estimate_motion(
    good_prev, good_next, K,
    ransac_threshold_px: float = 1.5,  # 픽셀 기준 임계 완화
    ransac_prob: float = 0.999,
    min_parallax_px: float = 0.8,      # 저시차 스킵 기준
    cheirality_min_ratio: float = 0.55 # Z>0 최소 비율 (완화)
):
    """
    Essential Matrix 기반 카메라 모션 추정 (안정화 통합판)
    Returns:
        R (3x3), t (3x1), E (3x3), stats(dict)
    """
    stats = {"parallax_px": 0.0, "in_pts": 0, "pose_ok": False, "cheirality_ratio": 0.0}

    if K is None:
        raise ValueError("❌ K 필요")
    if good_prev is None or good_next is None or len(good_prev) < 8 or len(good_next) < 8:
        return np.eye(3), np.zeros((3, 1)), None, stats

    prev_xy = good_prev.reshape(-1, 2).astype(np.float32)
    next_xy = good_next.reshape(-1, 2).astype(np.float32)
    stats["in_pts"] = int(len(prev_xy))

    # 1) 저시차/회전 장면 스킵
    parallax = _mean_parallax(prev_xy, next_xy)
    stats["parallax_px"] = parallax
    if parallax < min_parallax_px:
        # 병진이 거의 없으면 E/triangulation 불안정 → Pose 보류
        return np.eye(3), np.zeros((3, 1)), None, stats

    # 2) Essential Matrix (RANSAC) — 임계 완화 + 정규화
    E, mask = cv2.findEssentialMat(
        next_xy, prev_xy, K,
        method=cv2.RANSAC, prob=ransac_prob, threshold=ransac_threshold_px
    )
    if E is None or mask is None:
        return np.eye(3), np.zeros((3, 1)), None, stats
    E = E / (np.linalg.norm(E) + 1e-12)

    # 3) Pose 복원
    _, R, t, pose_mask = cv2.recoverPose(E, next_xy, prev_xy, K)

    # 4) 체이라리티 검사 + t 반전 시도
    p1n = cv2.undistortPoints(prev_xy.reshape(-1, 1, 2), K, None)
    p2n = cv2.undistortPoints(next_xy.reshape(-1, 1, 2), K, None)

    P0 = np.hstack([np.eye(3), np.zeros((3, 1))])
    P1 = np.hstack([R, t])

    def _pos_ratio(P0, P1, p1n, p2n):
        X = cv2.triangulatePoints(P0, P1, p1n, p2n)
        X /= (X[3] + 1e-12)
        return float(np.sum(X[2] > 0) / X.shape[1])

    ratio = _pos_ratio(P0, P1, p1n, p2n)

    if ratio < cheirality_min_ratio:
        # t 반전 시도
        t_inv = -t
        ratio_inv = _pos_ratio(P0, np.hstack([R, t_inv]), p1n, p2n)
        if ratio_inv > ratio:
            t, ratio = t_inv, ratio_inv

    stats["cheirality_ratio"] = ratio
    if ratio < cheirality_min_ratio:
        # 여전히 불안정 → Pose 보류
        return np.eye(3), np.zeros((3, 1)), E, stats

    # 5) 인라이어 재정제 (병진 충분할 때 방향 필터 사용)
    use_dir = parallax > 2.0
    prev_ref, next_ref = refine_inliers(prev_xy, next_xy, E, K, use_dir_filter=use_dir, drop_top_percent=20)

    # (선택) 재정제 후 다시 한 번 E/pose 갱신해도 됨—경량화를 위해 생략 가능
    stats["pose_ok"] = True
    return R, t, E, stats
