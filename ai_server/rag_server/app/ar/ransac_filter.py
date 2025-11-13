# import cv2
# import numpy as np

# def ransac_filter(
#     good_prev, good_next,
#     K=None, distCoeffs=None,
#     threshold=1.0, prob=0.999,
#     use_dir_filter=True,        # 전역 방향 필터
#     dir_cos_thresh=0.7,         # 전역 방향과의 코사인 유사도 임계값
#     use_grid_filter=True,       # 그리드 일관성 필터
#     grid_size=(8, 6),
#     sigma_scale=1.5,            # (평균 + k*σ) 초과 셀 제거
#     frame_shape=None,           # (H,W). 없으면 좌표로 추정
#     visualize=False, frame=None
# ):
#     """
#     RANSAC → Global direction filter → Grid coherence filter
#     Returns: inlier_prev, inlier_next, F, final_mask(bool over good_prev)
#     """

#     # 1) 입력/형상
#     if good_prev is None or good_next is None: return np.array([]), np.array([]), None, None
#     if len(good_prev) < 8 or len(good_next) < 8: return np.array([]), np.array([]), None, None
#     good_prev = np.squeeze(good_prev); good_next = np.squeeze(good_next)

#     # 2) (옵션) 보정 좌표계
#     if K is not None:
#         gp = cv2.undistortPoints(good_prev, K, distCoeffs)
#         gn = cv2.undistortPoints(good_next, K, distCoeffs)
#         fx, fy = K[0,0], K[1,1]
#         thr = threshold / np.mean([fx, fy])   # 1px ≈ 1/f
#     else:
#         gp, gn = good_prev, good_next
#         thr = threshold

#     # 3) RANSAC (F)
#     F, mask = cv2.findFundamentalMat(gp, gn, cv2.FM_RANSAC, ransacReprojThreshold=thr, confidence=prob)
#     if mask is None or np.count_nonzero(mask) < 8:
#         F, mask = cv2.findFundamentalMat(gp, gn, cv2.FM_RANSAC, ransacReprojThreshold=thr*1.5, confidence=prob)
#     if F is None or F.shape != (3,3) or np.linalg.matrix_rank(F) < 2:
#         return np.array([]), np.array([]), None, None

#     mask = mask.ravel().astype(bool)
#     inlier_prev = good_prev[mask]
#     inlier_next = good_next[mask]

#     if len(inlier_prev) < 8:
#         return np.array([]), np.array([]), F, mask  # 최소 방어

#     # === 공통: flow / magnitude / unit ===
#     flow = inlier_next - inlier_prev
#     mags = np.linalg.norm(flow, axis=1)
#     unit = flow / (mags[:,None] + 1e-6)

#     # 4) 전역 방향 필터 (방향이 전역과 다르면 제거)
#     if use_dir_filter:
#         global_dir = unit.mean(axis=0)
#         n = np.linalg.norm(global_dir)
#         if n > 1e-8: global_dir /= n
#         # 코사인 유사도
#         cos_sim = (unit @ global_dir) / (np.linalg.norm(global_dir) + 1e-6)
#         keep_dir = cos_sim > dir_cos_thresh
#         # 업데이트
#         idx = np.where(mask)[0]
#         mask_temp = np.zeros_like(mask, dtype=bool)
#         mask_temp[idx[keep_dir]] = True
#         mask = mask_temp
#         inlier_prev = good_prev[mask]
#         inlier_next = good_next[mask]
#         if len(inlier_prev) < 8:
#             return inlier_prev, inlier_next, F, mask

#         # flow 갱신
#         flow = inlier_next - inlier_prev
#         mags = np.linalg.norm(flow, axis=1)
#         unit = flow / (mags[:,None] + 1e-6)

#     # 5) 그리드 일관성 필터 (방향/크기 결합 통계)
#     if use_grid_filter and len(inlier_prev) >= 8:
#         # 프레임 크기 추정
#         if frame_shape is not None:
#             H, W = frame_shape[:2]
#         elif frame is not None:
#             H, W = frame.shape[:2]
#         else:
#             # 좌표 기반 추정(여유 padding)
#             W = int(max(good_prev[:,0].max(), good_next[:,0].max()) + 2)
#             H = int(max(good_prev[:,1].max(), good_next[:,1].max()) + 2)

#         cols, rows = grid_size
#         cw, ch = W/cols, H/rows

#         # 각 셀: 방향 일관성 + 크기 가중 평균
#         # 방향 일관성 = 동일 셀 내 평균 방향 벡터의 L2 norm (0~1)
#         cell_dir = np.zeros((rows, cols, 2), dtype=float)
#         cell_wsum = np.zeros((rows, cols), dtype=float)
#         cell_cnt  = np.zeros((rows, cols), dtype=int)

#         # 약한 가중치: 너무 큰 이동의 왜곡 줄이기 위해 sqrt
#         w = np.sqrt(mags + 1e-6)

#         for u, p, weight in zip(unit, inlier_prev, w):
#             cx, cy = int(p[0] // cw), int(p[1] // ch)
#             if 0 <= cx < cols and 0 <= cy < rows:
#                 cell_dir[cy, cx] += u * weight
#                 cell_wsum[cy, cx] += weight
#                 cell_cnt[cy, cx]  += 1

#         valid = cell_cnt > 0
#         # 평균 방향 벡터의 크기(0~1): 클수록 방향 일관성이 높음(=배경일 확률↑)
#         coherence = np.zeros((rows, cols), dtype=float)
#         coherence[valid] = np.linalg.norm(cell_dir[valid] / (cell_wsum[valid,None] + 1e-6), axis=1)

#         # 통계 임계값 (평균 - k*σ 미만: 일관성 낮음 → 제거)
#         vals = coherence[valid]
#         mu, sigma = np.mean(vals), np.std(vals)
#         thr_coh = mu - sigma_scale * sigma  # 낮으면 제거
#         remove_cells = coherence < thr_coh

#         # 점별 keep
#         keep = []
#         for p in inlier_prev:
#             cx, cy = int(p[0] // cw), int(p[1] // ch)
#             if 0 <= cx < cols and 0 <= cy < rows:
#                 keep.append(not remove_cells[cy, cx])
#             else:
#                 keep.append(False)
#         keep = np.asarray(keep, dtype=bool)

#         # 최종 마스크 반영
#         idx = np.where(mask)[0]
#         m2 = np.zeros_like(mask, dtype=bool)
#         m2[idx[keep]] = True
#         mask = m2
#         inlier_prev = good_prev[mask]
#         inlier_next = good_next[mask]

#     # 6) 시각화(선택)
#     if visualize and frame is not None:
#         vis = frame.copy()
#         for (p1, p2, m) in zip(good_prev, good_next, mask):
#             color = (0,255,0) if m else (0,0,255)
#             cv2.arrowedLine(vis, tuple(p1.astype(int)), tuple(p2.astype(int)), color, 1, tipLength=0.25)
#         cv2.imshow("RANSAC + Dir + Grid", vis); cv2.waitKey(1)

#     return inlier_prev, inlier_next, F, mask
import cv2
import numpy as np


# ==========================================================
# 🧩 (공통) Optical Flow 벡터 계산 유틸
# ==========================================================
def _compute_flow(p_prev, p_next):
    """
    두 점 집합(prev, next)에 대해:
    - flow : 각 점의 (dx,dy)
    - mags : flow의 크기(속력)
    - unit : flow 방향 단위 벡터
    
    Optical Flow 기반 모든 후처리 필터의 입력이 되는 기본 파생값.
    """
    flow = p_next - p_prev
    mags = np.linalg.norm(flow, axis=1)
    unit = flow / (mags[:, None] + 1e-6)   # 방향 벡터 normalize
    return flow, mags, unit


# ==========================================================
# 🧩 1) Fundamental Matrix 기반 RANSAC 처리
# ==========================================================
def _ransac_F(gp, gn, threshold, prob):
    """
    OpenCV의 Fundamental Matrix RANSAC을 사용하여 
    픽셀 좌표 기반 Outlier 제거.
    
    왜 F-RANSAC?
    - Rotation/Translation + depth 변화가 섞여 있는 일반적인 상황에서도 적용 가능
    - Essential Mat보다 안정성 ↑ (N=8 이상이면 F는 항상 추정 가능)
    - 곧 Essential로 변환하는 경우도 있지만, 첫 단계의 outlier 제거는 F가 더 robust함
    """

    F, mask = cv2.findFundamentalMat(
        gp, gn,
        cv2.FM_RANSAC,
        ransacReprojThreshold=threshold,
        confidence=prob
    )

    # 첫 RANSAC에서 심하게 탄다면 threshold 늘려서 보정
    if mask is None or np.count_nonzero(mask) < 8:
        F, mask = cv2.findFundamentalMat(
            gp, gn,
            cv2.FM_RANSAC,
            ransacReprojThreshold=threshold * 1.5,
            confidence=prob
        )

    # 실패 시 None 반환
    if F is None or mask is None or np.count_nonzero(mask) < 8:
        return None, None

    return F, mask.ravel().astype(bool)


# ==========================================================
# 🧩 2) "전역 흐름 방향" 기반 필터
# ==========================================================
def _direction_filter(prev, next, mask, gp, gn, cos_thresh):
    """
    RANSAC 이후 남은 inlier들 중에서도:
    - 전체적인 Optical Flow의 '전역 방향'과
    - 개별 Optical Flow의 방향이 지나치게 다르면 제거하는 과정.

    왜 필요?
    → 움직이는 객체(outlier) or 플리커 오류 등은 flow의 방향이 배경과 다르기 때문.
    """

    if len(prev) < 8:
        return mask, prev, next

    # 전체 흐름 계산
    flow, mags, unit = _compute_flow(prev, next)
    global_flow = flow.mean(axis=0)
    global_mag = np.linalg.norm(global_flow)

    # global flow가 너무 작으면 (회전/정지/플리커 구간)
    # 방향 필터는 적용하면 안 됨
    if global_mag < 0.5:
        return mask, prev, next

    # 전역 방향 벡터
    global_dir = global_flow / (global_mag + 1e-6)

    # 각 포인트 flow 방향과 전역 방향의 cos similarity(유사도)
    cos_sim = unit @ global_dir

    # 기준보다 낮으면 제거
    local_keep = cos_sim > cos_thresh

    # 기존 전체 마스크를 업데이트
    idx = np.where(mask)[0]
    new_mask = np.zeros_like(mask, dtype=bool)
    new_mask[idx[local_keep]] = True
    mask = new_mask

    # 최종 살아남은 좌표만 추출
    prev = gp[mask]
    next = gn[mask]

    return mask, prev, next


# ==========================================================
# 🧩 3) 그리드 기반 일관성 필터 (셀 단위 outlier 제거)
# ==========================================================
def _grid_filter(prev, next, mask, gp, gn,
                 frame_shape, grid_size,
                 sigma_scale, min_inliers):
    """
    프레임을 grid_size 만큼 나눈 뒤,
    각 셀을 기준으로 flow의 '일관성(coherence)'과 '크기(mag)'를 통계를 통해 필터링.

    동작 방식:
    1) 화면을 (cols x rows) 셀로 나눔
    2) 각 셀 내부에서:
        - flow 단위 벡터들의 평균 = coherence(방향 일관성)
        - flow 크기의 평균 = magnitude 평균
    3) coherence가 너무 낮거나, magnitude가 너무 큰 셀은 전체 outlier로 판단하고 제거

    이유:
    → moving object(예: 지나가는 사람) 포함 셀은
      - 방향 coherence 낮음
      - magnitude 지나치게 큼  
      → 따라서 해당 셀의 모든 점들을 한 번에 제거 가능
    """

    if len(prev) < min_inliers:
        # inlier 부족할 때 grid filtering은 무의미
        return mask, prev, next

    H, W = frame_shape[:2]
    cols, rows = grid_size
    cw, ch = W / cols, H / rows

    # flow 계산
    flow, mags, unit = _compute_flow(prev, next)

    # 셀별 집계
    cell_dir = np.zeros((rows, cols, 2), float)
    cell_mag = np.zeros((rows, cols), float)
    cell_cnt = np.zeros((rows, cols), int)

    for u, m, p in zip(unit, mags, prev):
        x, y = p
        cx = int(x // cw)
        cy = int(y // ch)
        if 0 <= cx < cols and 0 <= cy < rows:
            cell_dir[cy, cx] += u
            cell_mag[cy, cx] += m
            cell_cnt[cy, cx] += 1

    valid = cell_cnt > 0

    # coherence = 같은 셀 내 flow들의 단위벡터 평균(norm)
    coherence = np.zeros((rows, cols), float)
    coherence[valid] = np.linalg.norm(
        cell_dir[valid] / (cell_cnt[valid, None] + 1e-6),
        axis=1
    )

    # magnitude 평균
    avg_mag = np.zeros((rows, cols), float)
    avg_mag[valid] = cell_mag[valid] / (cell_cnt[valid] + 1e-6)

    # 전체 coherence/mag의 통계 기반 제거 기준
    coh_vals = coherence[valid]
    mag_vals = avg_mag[valid]

    coh_mu, coh_sigma = coh_vals.mean(), coh_vals.std() + 1e-6
    mag_mu, mag_sigma = mag_vals.mean(), mag_vals.std() + 1e-6

    # 각 셀의 z-score 계산
    coh_z = (coherence - coh_mu) / coh_sigma
    mag_z = (avg_mag - mag_mu) / mag_sigma

    # coherence 낮거나 magnitude 큰 셀은 제거
    remove_cells = (coh_z < -sigma_scale) | (mag_z > sigma_scale)

    # 점별로 셀을 보고 살아남을지 결정
    keep_local = []
    for p in prev:
        x, y = p
        cx = int(x // cw)
        cy = int(y // ch)
        keep_local.append(not remove_cells[cy, cx])

    keep_local = np.asarray(keep_local, bool)

    # 최종 마스크 업데이트
    idx = np.where(mask)[0]
    new_mask = np.zeros_like(mask, bool)
    new_mask[idx[keep_local]] = True
    mask = new_mask

    prev = gp[mask]
    next = gn[mask]
    return mask, prev, next


# ==========================================================
# ⭐ 최종: RANSAC + 방향 필터 + 그리드 필터
# ==========================================================
def ransac_filter(
    good_prev,
    good_next,
    *,
    threshold=1.0,
    prob=0.999,
    use_dir_filter=True,
    dir_cos_thresh=0.5,
    use_grid_filter=True,
    grid_size=(8, 6),
    sigma_scale=2.0,
    min_inliers_for_grid=40,
    frame_shape=None
):
    """
    Optical Flow 기반 inlier 정제를 위한 강력한 3단계 필터:
    1) Fundamental RANSAC — 1차 outlier 제거
    2) Direction Filter — 전역 이동 방향 일관성
    3) Grid Filter — 공간적 moving-object 제거
    
    반환값:
    inlier_prev, inlier_next, F, mask
    """

    if good_prev is None or len(good_prev) < 8:
        return np.array([]), np.array([]), None, None

    gp = np.squeeze(good_prev).astype(np.float32)
    gn = np.squeeze(good_next).astype(np.float32)

    # --- Step 1: Fundamental RANSAC ---
    F, mask = _ransac_F(gp, gn, threshold, prob)
    if mask is None:
        return np.array([]), np.array([]), None, None

    prev = gp[mask]
    next = gn[mask]

    # --- Step 2: 방향 필터 ---
    if use_dir_filter:
        mask, prev, next = _direction_filter(
            prev, next, mask, gp, gn, dir_cos_thresh
        )

    # --- Step 3: 그리드 기반 필터 ---
    if use_grid_filter and frame_shape is not None:
        mask, prev, next = _grid_filter(
            prev, next, mask, gp, gn,
            frame_shape,
            grid_size,
            sigma_scale,
            min_inliers_for_grid
        )

    # 최종 반환 (LK처럼 shape (N,1,2) 유지)
    return (
        prev.reshape(-1,1,2).astype(np.float32),
        next.reshape(-1,1,2).astype(np.float32),
        F,
        mask
    )
