from typing import Tuple
import cv2
import numpy as np
import os
import time


# ==========================================================
# 🧩 내부 유틸
# ==========================================================
def _equalize_if_needed(gray: np.ndarray, enable: bool) -> np.ndarray:
    """조명 안정화를 위해 equalizeHist를 조건부 적용"""
    if not enable:
        return gray
    return cv2.equalizeHist(gray)


def _is_blurry(gray: np.ndarray, lap_var_thresh: float) -> bool:
    """Variance of Laplacian 기반 블러 판정"""
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return lap_var < lap_var_thresh


def _mask_valid_forward_backward(
    prev_pts: np.ndarray,
    next_pts: np.ndarray,
    back_pts: np.ndarray,
    status_fwd: np.ndarray,
    status_bwd: np.ndarray,
    fb_thresh: float
) -> np.ndarray:
    """Forward–Backward 오차와 status를 이용해 유효 포인트 마스크 반환"""
    st_f = status_fwd.flatten().astype(bool)
    st_b = status_bwd.flatten().astype(bool)
    fb_err = np.linalg.norm(prev_pts - back_pts, axis=2).reshape(-1)

    # 너무 빡세게 자르지 말고, confidence 기반 soft 필터
    # fb_thresh는 scale 역할 (값이 클수록 더 관대)
    conf = np.exp(-fb_err / max(fb_thresh, 1e-6))
    valid_idx = np.argsort(conf)[::-1][: int(len(conf) * 0.95)]
    valid = np.zeros_like(st_f, dtype=bool)
    valid[valid_idx] = True

    # NaN/Inf 방어
    nan_guard = (
        np.isfinite(next_pts.reshape(-1, 2)).all(axis=1)
        & np.isfinite(back_pts.reshape(-1, 2)).all(axis=1)
    )
    return valid & st_f & st_b & nan_guard


def _filter_by_lk_error(
    err_fwd: np.ndarray,
    base_mask: np.ndarray,
    iqr_scale: float = 3.0
) -> np.ndarray:
    """LK 전방 에러 기반 추가 필터링 (관대화 버전)"""
    err = err_fwd.reshape(-1)
    good_err = err[base_mask]
    if good_err.size == 0:
        return base_mask

    med = np.median(good_err)
    if med > 0:
        thresh = med * iqr_scale
    else:
        thresh = np.percentile(good_err, 95)

    refined = base_mask.copy()
    refined[base_mask] &= (err[base_mask] <= thresh)
    return refined


def _mean_flow(prev_pts: np.ndarray, next_pts: np.ndarray) -> float:
    """평균 이동량(px) 계산 (로그/디버그용)"""
    if prev_pts is None or next_pts is None or len(prev_pts) == 0:
        return 0.0
    d = np.linalg.norm(next_pts - prev_pts, axis=2).reshape(-1)
    return float(np.mean(d)) if d.size else 0.0


def _adaptive_large_motion_filter(
    prev_pts: np.ndarray,
    next_pts: np.ndarray,
    base_mask: np.ndarray,
    k: float = 2.5
) -> np.ndarray:
    """
    Optical Flow 개별 outlier 제거:
    |flow| > mean + k * std  인 점들을 제거.
    - prev_pts, next_pts: (N,1,2)
    - base_mask: 기존까지 살아남은 유효 포인트 마스크
    """
    if prev_pts is None or next_pts is None or len(prev_pts) == 0:
        return base_mask

    prev = prev_pts.reshape(-1, 2)
    nxt = next_pts.reshape(-1, 2)

    flow = np.linalg.norm(nxt - prev, axis=1)
    good_flow = flow[base_mask]

    if good_flow.size == 0:
        return base_mask

    mean = np.mean(good_flow)
    std = np.std(good_flow)

    # std가 0이면 모두 비슷한 이동 → 그대로 통과
    if std < 1e-6:
        return base_mask

    thresh = mean + k * std
    refined = base_mask.copy()
    refined[base_mask] &= (flow[base_mask] < thresh)
    return refined


# ==========================================================
# 🧭 메인 Optical Flow 추적 함수
# ==========================================================
def track_features(
    prev_gray: np.ndarray,
    cur_gray: np.ndarray,
    prev_pts: np.ndarray,
    *,
    fb_thresh: float = 2.0,                 # FB soft-filter 스케일
    large_motion_px: float = 100.0,         # 프레임 전체 평균 이동량이 이걸 넘으면 issue 저장
    enable_equalize: bool = False,
    blur_var_thresh: float = 12.0,          # 약한 블러 프레임도 통과
    lk_win_size: Tuple[int, int] = (25, 25),
    lk_max_level: int = 4,
    lk_term_criteria: Tuple[int, int, float] = (
        cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 0.03
    ),
    frame=None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Sparse LK Optical Flow로 특징점을 추적하고, 관대화된 필터링 + Adaptive Large Motion 필터를 적용합니다.

    Returns:
        prev_pts_valid : (M,1,2) float32
        next_pts_valid : (M,1,2) float32
        valid_mask     : (N,) uint8 (원본 prev_pts 기준 살아남은 인덱스)
    """
    # ---------- 입력 검증 ----------
    if prev_pts is None or len(prev_pts) == 0:
        return np.array([]), np.array([]), np.array([], dtype=np.uint8)
    if prev_gray is None or cur_gray is None:
        return np.array([]), np.array([]), np.array([], dtype=np.uint8)

    # ---------- 전처리 ----------
    cur_proc = _equalize_if_needed(cur_gray, enable_equalize)

    # 블러 프레임은 스킵 (완화 기준)
    if _is_blurry(cur_proc, blur_var_thresh):
        return np.array([]), np.array([]), np.array([], dtype=np.uint8)

    # ---------- LK Optical Flow ----------
    lk_params = dict(winSize=lk_win_size, maxLevel=lk_max_level, criteria=lk_term_criteria)
    next_pts, status_fwd, err_fwd = cv2.calcOpticalFlowPyrLK(
        prev_gray, cur_proc, prev_pts, None, **lk_params
    )
    if next_pts is None or status_fwd is None:
        return np.array([]), np.array([]), np.array([], dtype=np.uint8)

    # Backward
    back_pts, status_bwd, _ = cv2.calcOpticalFlowPyrLK(
        cur_proc, prev_gray, next_pts, None, **lk_params
    )
    if back_pts is None or status_bwd is None:
        return np.array([]), np.array([]), np.array([], dtype=np.uint8)

    # ---------- 1차 필터링: FB + LK error ----------
    valid = _mask_valid_forward_backward(prev_pts, next_pts, back_pts, status_fwd, status_bwd, fb_thresh)
    valid = _filter_by_lk_error(err_fwd, valid, iqr_scale=3.0)

    # ---------- 2차 필터링: Adaptive Large Motion (개별 outlier 제거) ----------
    valid = _adaptive_large_motion_filter(prev_pts, next_pts, valid, k=1.5)

    # ---------- 프레임 수준 large motion 감지 & 저장 (디버그용) ----------
    if np.count_nonzero(valid) >= 5:
        mean_flow = _mean_flow(prev_pts[valid], next_pts[valid])
        # if mean_flow > large_motion_px:
        #     print(f"⚠️ Large motion detected: mean={mean_flow:.1f}px (> {large_motion_px})")
        # ---------- 유효 포인트 결과 ----------
    if np.count_nonzero(valid) < 5:
        return np.array([]), np.array([]), np.array([], dtype=np.uint8)

    prev_valid = prev_pts[valid].reshape(-1, 1, 2).astype(np.float32)
    next_valid = next_pts[valid].reshape(-1, 1, 2).astype(np.float32)
    valid_mask = valid.astype(np.uint8)

    return prev_valid, next_valid, valid_mask


# ==========================================================
# ✅ 개선 요약
# ==========================================================
# • FB soft-filter (상위 85% confidence 유지)
# • LK error 기반 IQR 필터 (관대)
# • Adaptive Large Motion ( |flow| > mean + 1.5 * std 제거 )
# • blur_var_thresh  = 12.0   → 약한 블러 프레임 통과
# • winSize          = (25,25), maxLevel=4 → 큰 모션 대응
# • 프레임 평균 이동량이 large_motion_px 초과 시 issue 프레임 저장
#
# 🚀 효과:
#   - 개별 outlier 제거 → RANSAC inlier 비율 상승
#   - Tracking-lost 빈도 감소
#   - 큰 움직임/플리커/오류 벡터 대응 향상
# ==========================================================
