import cv2
import numpy as np


def _mean_parallax(prev_xy, next_xy):
    """평균 패럴럭스(px). Z 변화 감지 안정성 판단용."""
    return float(np.mean(np.linalg.norm(next_xy - prev_xy, axis=1)))


def _refine_inliers(prev_xy, next_xy, E, K):
    """
    Essential Matrix 기반 epipolar 정합 오차로 인라이어를 정제한다.
    방향/크기 기반 가벼운 필터 + epipolar 오차 정제.
    """
    flow = next_xy - prev_xy
    mags = np.linalg.norm(flow, axis=1)

    # 1) 방향 일관성 필터
    unit = flow / (mags[:, None] + 1e-6)
    mean_dir = unit.mean(axis=0)
    mean_dir /= (np.linalg.norm(mean_dir) + 1e-6)
    cos_sim = unit @ mean_dir
    dir_mask = cos_sim > 0.5

    prev_xy = prev_xy[dir_mask]
    next_xy = next_xy[dir_mask]
    flow = next_xy - prev_xy
    mags = np.linalg.norm(flow, axis=1)

    # 2) magnitude 필터 (이상치 제거)
    m, s = np.mean(mags), np.std(mags)
    mag_mask = np.abs(mags - m) < 2.0 * (s + 1e-6)

    prev_xy = prev_xy[mag_mask]
    next_xy = next_xy[mag_mask]

    # 3) Epipolar 오차 기반 정제
    p1 = cv2.undistortPoints(prev_xy.reshape(-1, 1, 2), K, None)
    p2 = cv2.undistortPoints(next_xy.reshape(-1, 1, 2), K, None)

    x1 = np.hstack([p1[:, 0], np.ones((len(p1), 1))])
    x2 = np.hstack([p2[:, 0], np.ones((len(p2), 1))])

    err = np.abs(np.sum(x2 * (E @ x1.T).T, axis=1))
    keep = err < np.percentile(err, 80)

    return prev_xy[keep], next_xy[keep]


def estimate_motion(prev_pts, next_pts, K,
                    ransac_threshold_px=1.0,
                    min_parallax_px=0.5):
    """
    Essential Matrix 기반 모션(R, t) + Z 이동량 기반 scale 추정.

    반환:
        R, t, scale, stats(dict)
    """
    stats = {
        "pose_ok": False,
        "inliers": 0,
        "parallax": 0.0,
        "scale": 1.0
    }

    if prev_pts is None or next_pts is None or len(prev_pts) < 8:
        return np.eye(3), np.zeros((3, 1)), 1.0, stats

    prev_xy = prev_pts.reshape(-1, 2).astype(np.float32)
    next_xy = next_pts.reshape(-1, 2).astype(np.float32)

    # 1) 패럴럭스 검사 (Z 변화 없는 구간 막기)
    parallax = _mean_parallax(prev_xy, next_xy)
    stats["parallax"] = parallax
    if parallax < min_parallax_px:
        return np.eye(3), np.zeros((3, 1)), 1.0, stats

    # 2) Essential Matrix
    E, mask = cv2.findEssentialMat(
        prev_xy, next_xy, K,
        method=cv2.RANSAC,
        threshold=ransac_threshold_px,
        prob=0.999
    )
    if E is None or mask is None:
        return np.eye(3), np.zeros((3, 1)), 1.0, stats

    # 3) Recover Pose
    _, R, t, pose_mask = cv2.recoverPose(E, prev_xy, next_xy, K)

    # 4) 인라이어 재정제
    prev_ref, next_ref = _refine_inliers(prev_xy, next_xy, E, K)
    stats["inliers"] = len(prev_ref)

    if len(prev_ref) < 8:
        return np.eye(3), np.zeros((3, 1)), 1.0, stats

    # 5) 최종 scale 추정 → Z 방향 이동량 사용
    # t는 단위 벡터이지만, Z 방향 비율은 scale 비례값으로 충분
    scale = abs(float(t[2]))

    stats["scale"] = scale
    stats["pose_ok"] = True

    return R, t, scale, stats
