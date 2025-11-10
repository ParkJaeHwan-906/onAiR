import cv2
import numpy as np

def ransac_filter(
    good_prev, good_next,
    K=None, distCoeffs=None,
    threshold=1.0, prob=0.999,
    use_dir_filter=True,        # 전역 방향 필터
    dir_cos_thresh=0.7,         # 전역 방향과의 코사인 유사도 임계값
    use_grid_filter=True,       # 그리드 일관성 필터
    grid_size=(8, 6),
    sigma_scale=1.5,            # (평균 + k*σ) 초과 셀 제거
    frame_shape=None,           # (H,W). 없으면 좌표로 추정
    visualize=False, frame=None
):
    """
    RANSAC → Global direction filter → Grid coherence filter
    Returns: inlier_prev, inlier_next, F, final_mask(bool over good_prev)
    """

    # 1) 입력/형상
    if good_prev is None or good_next is None: return np.array([]), np.array([]), None, None
    if len(good_prev) < 8 or len(good_next) < 8: return np.array([]), np.array([]), None, None
    good_prev = np.squeeze(good_prev); good_next = np.squeeze(good_next)

    # 2) (옵션) 보정 좌표계
    if K is not None:
        gp = cv2.undistortPoints(good_prev, K, distCoeffs)
        gn = cv2.undistortPoints(good_next, K, distCoeffs)
        fx, fy = K[0,0], K[1,1]
        thr = threshold / np.mean([fx, fy])   # 1px ≈ 1/f
    else:
        gp, gn = good_prev, good_next
        thr = threshold

    # 3) RANSAC (F)
    F, mask = cv2.findFundamentalMat(gp, gn, cv2.FM_RANSAC, ransacReprojThreshold=thr, confidence=prob)
    if mask is None or np.count_nonzero(mask) < 8:
        F, mask = cv2.findFundamentalMat(gp, gn, cv2.FM_RANSAC, ransacReprojThreshold=thr*1.5, confidence=prob)
    if F is None or F.shape != (3,3) or np.linalg.matrix_rank(F) < 2:
        return np.array([]), np.array([]), None, None

    mask = mask.ravel().astype(bool)
    inlier_prev = good_prev[mask]
    inlier_next = good_next[mask]

    if len(inlier_prev) < 8:
        return np.array([]), np.array([]), F, mask  # 최소 방어

    # === 공통: flow / magnitude / unit ===
    flow = inlier_next - inlier_prev
    mags = np.linalg.norm(flow, axis=1)
    unit = flow / (mags[:,None] + 1e-6)

    # 4) 전역 방향 필터 (방향이 전역과 다르면 제거)
    if use_dir_filter:
        global_dir = unit.mean(axis=0)
        n = np.linalg.norm(global_dir)
        if n > 1e-8: global_dir /= n
        # 코사인 유사도
        cos_sim = (unit @ global_dir) / (np.linalg.norm(global_dir) + 1e-6)
        keep_dir = cos_sim > dir_cos_thresh
        # 업데이트
        idx = np.where(mask)[0]
        mask_temp = np.zeros_like(mask, dtype=bool)
        mask_temp[idx[keep_dir]] = True
        mask = mask_temp
        inlier_prev = good_prev[mask]
        inlier_next = good_next[mask]
        if len(inlier_prev) < 8:
            return inlier_prev, inlier_next, F, mask

        # flow 갱신
        flow = inlier_next - inlier_prev
        mags = np.linalg.norm(flow, axis=1)
        unit = flow / (mags[:,None] + 1e-6)

    # 5) 그리드 일관성 필터 (방향/크기 결합 통계)
    if use_grid_filter and len(inlier_prev) >= 8:
        # 프레임 크기 추정
        if frame_shape is not None:
            H, W = frame_shape[:2]
        elif frame is not None:
            H, W = frame.shape[:2]
        else:
            # 좌표 기반 추정(여유 padding)
            W = int(max(good_prev[:,0].max(), good_next[:,0].max()) + 2)
            H = int(max(good_prev[:,1].max(), good_next[:,1].max()) + 2)

        cols, rows = grid_size
        cw, ch = W/cols, H/rows

        # 각 셀: 방향 일관성 + 크기 가중 평균
        # 방향 일관성 = 동일 셀 내 평균 방향 벡터의 L2 norm (0~1)
        cell_dir = np.zeros((rows, cols, 2), dtype=float)
        cell_wsum = np.zeros((rows, cols), dtype=float)
        cell_cnt  = np.zeros((rows, cols), dtype=int)

        # 약한 가중치: 너무 큰 이동의 왜곡 줄이기 위해 sqrt
        w = np.sqrt(mags + 1e-6)

        for u, p, weight in zip(unit, inlier_prev, w):
            cx, cy = int(p[0] // cw), int(p[1] // ch)
            if 0 <= cx < cols and 0 <= cy < rows:
                cell_dir[cy, cx] += u * weight
                cell_wsum[cy, cx] += weight
                cell_cnt[cy, cx]  += 1

        valid = cell_cnt > 0
        # 평균 방향 벡터의 크기(0~1): 클수록 방향 일관성이 높음(=배경일 확률↑)
        coherence = np.zeros((rows, cols), dtype=float)
        coherence[valid] = np.linalg.norm(cell_dir[valid] / (cell_wsum[valid,None] + 1e-6), axis=1)

        # 통계 임계값 (평균 - k*σ 미만: 일관성 낮음 → 제거)
        vals = coherence[valid]
        mu, sigma = np.mean(vals), np.std(vals)
        thr_coh = mu - sigma_scale * sigma  # 낮으면 제거
        remove_cells = coherence < thr_coh

        # 점별 keep
        keep = []
        for p in inlier_prev:
            cx, cy = int(p[0] // cw), int(p[1] // ch)
            if 0 <= cx < cols and 0 <= cy < rows:
                keep.append(not remove_cells[cy, cx])
            else:
                keep.append(False)
        keep = np.asarray(keep, dtype=bool)

        # 최종 마스크 반영
        idx = np.where(mask)[0]
        m2 = np.zeros_like(mask, dtype=bool)
        m2[idx[keep]] = True
        mask = m2
        inlier_prev = good_prev[mask]
        inlier_next = good_next[mask]

    # 6) 시각화(선택)
    if visualize and frame is not None:
        vis = frame.copy()
        for (p1, p2, m) in zip(good_prev, good_next, mask):
            color = (0,255,0) if m else (0,0,255)
            cv2.arrowedLine(vis, tuple(p1.astype(int)), tuple(p2.astype(int)), color, 1, tipLength=0.25)
        cv2.imshow("RANSAC + Dir + Grid", vis); cv2.waitKey(1)

    return inlier_prev, inlier_next, F, mask
