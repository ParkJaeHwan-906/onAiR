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
