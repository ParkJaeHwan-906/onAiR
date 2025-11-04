# 📄 motion_estimator.py — Depth Proxy + Normalized 컬러맵 데이터 통합 버전
import cv2
import numpy as np


def _mean_parallax(prev_xy: np.ndarray, next_xy: np.ndarray) -> float:
    """두 프레임 간 평균 픽셀 이동량(시차) 계산."""
    return float(np.mean(np.linalg.norm(next_xy - prev_xy, axis=1)))


def refine_inliers(good_prev, good_next, E, K, use_dir_filter=True, drop_top_percent=20):
    """
    Essential Matrix 이후 인라이어 재정제:
    - (옵션) Optical Flow 방향/크기 필터
    - Epipolar 재투영 오차 기반 상위 퍼센트 제거
    """
    if good_prev is None or good_next is None:
        return np.array([]), np.array([])
    if len(good_prev) < 8:
        return good_prev, good_next

    prev_xy = good_prev.reshape(-1, 2)
    next_xy = good_next.reshape(-1, 2)

    flow = next_xy - prev_xy
    if use_dir_filter and len(flow) >= 8:
        # 방향 일관성 필터
        unit = flow / (np.linalg.norm(flow, axis=1, keepdims=True) + 1e-6)
        mean_dir = unit.mean(axis=0)
        mean_dir /= (np.linalg.norm(mean_dir) + 1e-6)
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

    # Epipolar 제약 기반 오차 정제
    p1n = cv2.undistortPoints(prev_xy.reshape(-1, 1, 2), K, None)
    p2n = cv2.undistortPoints(next_xy.reshape(-1, 1, 2), K, None)
    x1 = np.hstack([p1n[:, 0], np.ones((len(p1n), 1))])
    x2 = np.hstack([p2n[:, 0], np.ones((len(p2n), 1))])
    err = np.abs(np.sum(x2 * (E @ x1.T).T, axis=1))

    keep = err < np.percentile(err, 100 - drop_top_percent)
    return prev_xy[keep].reshape(-1, 2), next_xy[keep].reshape(-1, 2)


def estimate_motion(
    good_prev, good_next, K,
    ransac_threshold_px: float = 1.5,
    ransac_prob: float = 0.999,
    min_parallax_px: float = 0.8,
    cheirality_min_ratio: float = 0.55
):
    """
    Essential Matrix 기반 카메라 모션 추정 + 깊이 프록시 계산
    Returns:
        R (3x3), t (3x1), E (3x3), stats(dict)
    """
    stats = {
        "parallax_px": 0.0,
        "in_pts": 0,
        "pose_ok": False,
        "cheirality_ratio": 0.0,
        "depth_proxy_mean": 0.0,
        "depth_proxy_std": 0.0,
        "depth_proxy_per_point": np.array([]),
        "depth_proxy_normalized": np.array([]),
        "inlier_prev_ref": np.array([]),
    }

    if K is None:
        raise ValueError("❌ K 필요")
    if good_prev is None or good_next is None or len(good_prev) < 8:
        return np.eye(3), np.zeros((3, 1)), None, stats

    prev_xy = good_prev.reshape(-1, 2).astype(np.float32)
    next_xy = good_next.reshape(-1, 2).astype(np.float32)
    stats["in_pts"] = int(len(prev_xy))

    # 1️⃣ 저시차 / 회전 장면 스킵
    parallax = _mean_parallax(prev_xy, next_xy)
    stats["parallax_px"] = parallax
    if parallax < min_parallax_px:
        return np.eye(3), np.zeros((3, 1)), None, stats

    # 2️⃣ Essential Matrix 계산
    E, mask = cv2.findEssentialMat(
        next_xy, prev_xy, K,
        method=cv2.RANSAC, prob=ransac_prob, threshold=ransac_threshold_px
    )
    if E is None or mask is None:
        return np.eye(3), np.zeros((3, 1)), None, stats
    E = E / (np.linalg.norm(E) + 1e-12)

    # 3️⃣ Pose 복원
    _, R, t, pose_mask = cv2.recoverPose(E, next_xy, prev_xy, K)

    # 4️⃣ 체이라리티 검사
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
        t_inv = -t
        ratio_inv = _pos_ratio(P0, np.hstack([R, t_inv]), p1n, p2n)
        if ratio_inv > ratio:
            t, ratio = t_inv, ratio_inv
    stats["cheirality_ratio"] = ratio

    if ratio < cheirality_min_ratio:
        return np.eye(3), np.zeros((3, 1)), E, stats

    # 5️⃣ 인라이어 재정제
    use_dir = parallax > 2.0
    prev_ref, next_ref = refine_inliers(prev_xy, next_xy, E, K, use_dir_filter=use_dir)
    stats["inlier_prev_ref"] = prev_ref.copy()

    # 6️⃣ 회전 보정 + 패럴럭스 기반 깊이 프록시 계산
    if len(prev_ref) >= 8:
        H_R = K @ R @ np.linalg.inv(K)
        prev_h = cv2.convertPointsToHomogeneous(prev_ref.reshape(-1, 1, 2)).reshape(-1, 3).T
        pred_h = H_R @ prev_h
        pred_xy = (pred_h[:2] / (pred_h[2:3] + 1e-6)).T

        parallax_vec = next_ref - pred_xy
        parallax_len = np.linalg.norm(parallax_vec, axis=1)

        # FOE (Focus of Expansion) 계산
        if abs(float(t[2])) > 1e-6:
            foe_norm = np.array([float(t[0] / t[2]), float(t[1] / t[2])], dtype=np.float32)
            foe_px_h = K @ np.array([foe_norm[0], foe_norm[1], 1.0], dtype=np.float32)
            foe_px = foe_px_h[:2] / foe_px_h[2]
        else:
            foe_px = None

        if foe_px is not None:
            dist_to_foe = np.linalg.norm(prev_ref - foe_px[None, :], axis=1) + 1e-6
            depth_proxy = parallax_len / dist_to_foe
        else:
            depth_proxy = parallax_len

        # 프록시 통계 저장
        stats["depth_proxy_mean"] = float(np.mean(depth_proxy))
        stats["depth_proxy_std"] = float(np.std(depth_proxy))
        stats["depth_proxy_per_point"] = depth_proxy.astype(np.float32)

        # 정규화 값 미리 계산 (시각화용)
        dp_norm = (depth_proxy - np.min(depth_proxy)) / (np.max(depth_proxy) - np.min(depth_proxy) + 1e-6)
        stats["depth_proxy_normalized"] = dp_norm.astype(np.float32)

                # ✅ Sparse → Dense Depth 보간 로직 추가
        # --- 해상도 설정 (640x480 기본, 필요 시 자동 감지 가능)
        h, w = 480, 640
        sparse_depth = np.zeros((h, w), dtype=np.float32)

        # 특징점 위치에 깊이값 찍기
        for (x, y), z in zip(prev_ref, depth_proxy):
            xi, yi = int(round(x)), int(round(y))
            if 0 <= xi < w and 0 <= yi < h:
                sparse_depth[yi, xi] = z

        # 마스크 생성 (깊이 없는 영역)
        mask = (sparse_depth == 0).astype(np.uint8)

        # OpenCV inpaint로 주변 깊이값 보간
        dense_depth = cv2.inpaint(sparse_depth, mask, 3, cv2.INPAINT_TELEA)

        # 컬러맵 생성 (시각화용)
        dense_norm = cv2.normalize(dense_depth, None, 0, 1, cv2.NORM_MINMAX)
        dense_colormap = cv2.applyColorMap(
            (dense_norm * 255).astype(np.uint8), cv2.COLORMAP_JET
        )

        # 통계 및 결과 저장
        stats["depth_proxy_dense"] = dense_depth
        stats["depth_colormap"] = dense_colormap

    stats["pose_ok"] = True
    return R, t, E, stats
