# import cv2
# import numpy as np


# def _mean_parallax(prev_xy: np.ndarray, next_xy: np.ndarray) -> float:
#     return float(np.mean(np.linalg.norm(next_xy - prev_xy, axis=1)))


# def refine_inliers(good_prev, good_next, E, K, use_dir_filter=True, drop_top_percent=20):
#     if good_prev is None or good_next is None:
#         return np.array([]), np.array([])
#     if len(good_prev) < 8:
#         return good_prev, good_next

#     prev_xy = good_prev.reshape(-1, 2)
#     next_xy = good_next.reshape(-1, 2)
#     flow = next_xy - prev_xy

#     # 방향 일관성 필터
#     if use_dir_filter and len(flow) >= 8:
#         unit = flow / (np.linalg.norm(flow, axis=1, keepdims=True) + 1e-6)
#         mean_dir = unit.mean(axis=0)
#         mean_dir /= (np.linalg.norm(mean_dir) + 1e-6)
#         cos_sim = unit @ mean_dir
#         dir_mask = cos_sim > 0.7
#         prev_xy, next_xy = prev_xy[dir_mask], next_xy[dir_mask]
#         flow = flow[dir_mask]

#     # 크기 통계 필터
#     if len(flow) >= 8:
#         mag = np.linalg.norm(flow, axis=1)
#         m, s = np.mean(mag), np.std(mag)
#         mag_mask = np.abs(mag - m) < 1.5 * (s + 1e-6)
#         prev_xy, next_xy = prev_xy[mag_mask], next_xy[mag_mask]

#     # Epipolar 오차 정제
#     p1n = cv2.undistortPoints(prev_xy.reshape(-1, 1, 2), K, None)
#     p2n = cv2.undistortPoints(next_xy.reshape(-1, 1, 2), K, None)
#     x1 = np.hstack([p1n[:, 0], np.ones((len(p1n), 1))])
#     x2 = np.hstack([p2n[:, 0], np.ones((len(p2n), 1))])
#     err = np.abs(np.sum(x2 * (E @ x1.T).T, axis=1))
#     keep = err < np.percentile(err, 100 - drop_top_percent)
#     return prev_xy[keep], next_xy[keep]


# def estimate_motion(
#     good_prev, good_next, K,
#     ransac_threshold_px: float = 1.5,
#     ransac_prob: float = 0.999,
#     min_parallax_px: float = 0.8,
#     cheirality_min_ratio: float = 0.55
# ):
#     stats = {
#         "parallax_px": 0.0,
#         "in_pts": 0,
#         "pose_ok": False,
#         "cheirality_ratio": 0.0,
#         "depth_proxy_mean": 0.0,
#         "depth_proxy_std": 0.0,
#         "depth_proxy_per_point": np.array([]),
#         "depth_triangulated": np.array([]),
#         "depth_combined": np.array([]),
#         "scale": 1.0,
#         "inlier_prev_ref": np.array([]),
#     }

#     if K is None:
#         raise ValueError("❌ K 필요")
#     if good_prev is None or good_next is None or len(good_prev) < 8:
#         return np.eye(3), np.zeros((3, 1)), None, stats

#     prev_xy = good_prev.reshape(-1, 2).astype(np.float32)
#     next_xy = good_next.reshape(-1, 2).astype(np.float32)
#     stats["in_pts"] = len(prev_xy)

#     # 1️⃣ 평균 패럴럭스
#     parallax = _mean_parallax(prev_xy, next_xy)
#     stats["parallax_px"] = parallax
#     if parallax < min_parallax_px:
#         return np.eye(3), np.zeros((3, 1)), None, stats

#     # 2️⃣ Essential Matrix (순서 수정)
#     E, mask = cv2.findEssentialMat(
#         prev_xy, next_xy, K, method=cv2.RANSAC,
#         prob=ransac_prob, threshold=ransac_threshold_px
#     )
#     if E is None or mask is None:
#         return np.eye(3), np.zeros((3, 1)), None, stats
#     E /= (np.linalg.norm(E) + 1e-12)

#     # 3️⃣ Pose 복원
#     _, R, t, pose_mask = cv2.recoverPose(E, prev_xy, next_xy, K)

#     # 4️⃣ 체이라리티 검사
#     p1n = cv2.undistortPoints(prev_xy.reshape(-1, 1, 2), K, None).reshape(-1, 2)
#     p2n = cv2.undistortPoints(next_xy.reshape(-1, 1, 2), K, None).reshape(-1, 2)
#     x1, x2 = p1n.T, p2n.T

#     def _pos_ratio(P0, P1, x1, x2):
#         X = cv2.triangulatePoints(P0, P1, x1, x2)
#         X /= (X[3:4] + 1e-12)
#         return float(np.mean(X[2] > 0))

#     P0 = np.hstack([np.eye(3), np.zeros((3, 1))])
#     P1 = np.hstack([R, t])

#     ratio = _pos_ratio(P0, P1, x1, x2)
#     if ratio < cheirality_min_ratio:
#         t_inv = -t
#         ratio_inv = _pos_ratio(P0, np.hstack([R, t_inv]), x1, x2)
#         if ratio_inv > ratio:
#             t, ratio = t_inv, ratio_inv
#     stats["cheirality_ratio"] = ratio
#     if ratio < cheirality_min_ratio:
#         return np.eye(3), np.zeros((3, 1)), E, stats

#     # 5️⃣ 인라이어 재정제
#     use_dir = parallax > 2.0
#     prev_ref, next_ref = refine_inliers(prev_xy, next_xy, E, K, use_dir_filter=use_dir)
#     stats["inlier_prev_ref"] = prev_ref

#     # 6️⃣ 모노큘러 삼각측량 (상대 깊이)
#     if len(prev_ref) >= 8:
#         p1n = cv2.undistortPoints(prev_ref.reshape(-1, 1, 2), K, None).reshape(-1, 2)
#         p2n = cv2.undistortPoints(next_ref.reshape(-1, 1, 2), K, None).reshape(-1, 2)
#         x1, x2 = p1n.T, p2n.T

#         P0 = np.hstack([np.eye(3), np.zeros((3, 1))])
#         P1 = np.hstack([R, t])
#         X_h = cv2.triangulatePoints(P0, P1, x1, x2)
#         X = X_h / (X_h[3:4] + 1e-12)
#         Z = X[2, :]  # 깊이
#         Z[Z <= 0] = np.nan
#         stats["depth_triangulated"] = Z

#         # 7️⃣ 패럴럭스 기반 깊이 프록시 (기존 방식)
#         H_R = K @ R @ np.linalg.inv(K)
#         prev_h = cv2.convertPointsToHomogeneous(prev_ref.reshape(-1, 1, 2)).reshape(-1, 3).T
#         pred_h = H_R @ prev_h
#         pred_xy = (pred_h[:2] / (pred_h[2:3] + 1e-6)).T
#         parallax_vec = next_ref - pred_xy
#         parallax_len = np.linalg.norm(parallax_vec, axis=1)

#         foe_px = None
#         if abs(float(t[2])) > 1e-6:
#             foe_norm = np.array([float(t[0]/t[2]), float(t[1]/t[2])], dtype=np.float32)
#             foe_px_h = K @ np.array([foe_norm[0], foe_norm[1], 1.0], dtype=np.float32)
#             foe_px = (foe_px_h[:2] / foe_px_h[2]).astype(np.float32)

#         if foe_px is not None:
#             dist_to_foe = np.linalg.norm(prev_ref - foe_px[None, :], axis=1) + 1e-6
#             depth_proxy = parallax_len / dist_to_foe
#         else:
#             depth_proxy = parallax_len
#         stats["depth_proxy_per_point"] = depth_proxy

#         # 8️⃣ 깊이 융합 (삼각측량 + 프록시)
#         valid_mask = ~np.isnan(Z)
#         combined_depth = np.zeros_like(depth_proxy)
#         combined_depth[valid_mask] = 0.7 * Z[valid_mask] + 0.3 * depth_proxy[valid_mask]
#         combined_depth[~valid_mask] = depth_proxy[~valid_mask]
#         stats["depth_combined"] = combined_depth

#         # 9️⃣ 프레임별 스케일 추정 (EMA)
#         med_depth = np.nanmedian(combined_depth) + 1e-6
#         alpha, beta = 1.0, 0.9
#         if "scale_ema" not in estimate_motion.__dict__:
#             estimate_motion.scale_ema = alpha / med_depth
#         s_inst = alpha / med_depth
#         s = beta * estimate_motion.scale_ema + (1 - beta) * s_inst
#         estimate_motion.scale_ema = s
#         stats["scale"] = float(s)

#         # 10️⃣ 깊이 정규화
#         dp_norm = (combined_depth - np.nanmin(combined_depth)) / \
#                   (np.nanmax(combined_depth) - np.nanmin(combined_depth) + 1e-6)
#         stats["depth_proxy_mean"] = float(np.nanmean(combined_depth))
#         stats["depth_proxy_std"] = float(np.nanstd(combined_depth))
#         stats["depth_proxy_normalized"] = dp_norm.astype(np.float32)

#     stats["pose_ok"] = True
#     return R, t, E, stats
# motion_estimator.py
# ------------------------------------------------------------
# Essential Matrix 기반 카메라 모션(R, t) 및 scale 변화량 계산 모듈
# AR Marker scale 업데이트용 경량 버전
# ------------------------------------------------------------

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
