# motion_core.py
# ------------------------------------------------------------
# 📌 Optical Flow + RANSAC + Essential 기반
# 📌 AR Marker UI 이동(x,y) + Size(z) 계산
# ------------------------------------------------------------

import numpy as np
import cv2

from .feature_extractor import extract_features
from .feature_tracker import track_features
from .ransac_filter import ransac_filter
from .motion_estimator import estimate_motion


# ==========================================================
# 🔧 전역 상태
# ==========================================================
K = None
D = None

prev_gray = None
prev_pts = None

R_total = np.eye(3, dtype=np.float32)
t_total = np.zeros((3, 1), dtype=np.float32)

# Essential 기반 size 누적
size_acc = 1.0

# Optical Flow 평균 이동량(dx, dy)
last_flow_mean = np.array([0.0, 0.0], dtype=np.float32)


# ==========================================================
# 🔧 초기화 함수
# ==========================================================
def init(K_in, D_in=None):
    global K, D
    K = K_in.astype(np.float32)
    D = D_in.astype(np.float32) if D_in is not None else None
    print("📌 motion_core 초기화 완료")


# ==========================================================
# 🔧 Optical Flow 평균 이동 계산
# ==========================================================
def compute_flow_mean(prev_pts, next_pts):
    if len(prev_pts) == 0:
        return np.array([0.0, 0.0], dtype=np.float32)

    p1 = prev_pts.reshape(-1, 2)
    p2 = next_pts.reshape(-1, 2)
    flow = p2 - p1
    return np.mean(flow, axis=0).astype(np.float32)


# ==========================================================
# 🔧 클릭된 marker 좌표 업데이트
# ==========================================================
def update_marker_position(u, v):
    """
    Optical Flow 기반 이동 + Essential 기반 size 반영
    """
    global last_flow_mean, size_acc

    u_new = u - last_flow_mean[0]
    v_new = v - last_flow_mean[1]
    z_size = float(size_acc)

    return u_new, v_new, z_size


# ==========================================================
# 🔧 프레임 처리 (가장 중요한 메인 함수)
# ==========================================================
def process_frame(frame_bgr):
    """
    Optical Flow + RANSAC + Essential 처리 후
    상태를 업데이트하고 AR Marker 업데이트에 필요한 정보를 반환.

    return {
        "tracked": int,
        "inliers": int,
        "ransac_ratio": float,
        "size": float,
        "flow_mean": (dx, dy)
    }
    """
    global prev_gray, prev_pts
    global last_flow_mean, size_acc
    global R_total, t_total

    # Undistort
    if D is not None:
        frame = cv2.undistort(frame_bgr, K, D)
    else:
        frame = frame_bgr

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 1) 첫 프레임: 특징점만 추출
    if prev_gray is None:
        prev_pts, _ = extract_features(gray)
        prev_gray = gray.copy()
        return {
            "tracked": len(prev_pts),
            "inliers": len(prev_pts),
            "ransac_ratio": 100.0,
            "size": float(size_acc),
            "flow_mean": (0.0, 0.0),
        }

    # 2) Optical Flow
    prev_valid, next_valid, _ = track_features(
        prev_gray, gray, prev_pts,
        fb_thresh=2.0,
        blur_var_thresh=12.0,
        lk_win_size=(25, 25),
        lk_max_level=4,
        frame=frame
    )

    if len(prev_valid) == 0:
        prev_pts, _ = extract_features(gray)
        prev_gray = gray.copy()
        last_flow_mean = np.array([0.0, 0.0], dtype=np.float32)
        return {
            "tracked": 0,
            "inliers": 0,
            "ransac_ratio": 0.0,
            "size": float(size_acc),
            "flow_mean": (0.0, 0.0),
        }

    # Optical Flow mean
    flow_mean = compute_flow_mean(prev_valid, next_valid)
    last_flow_mean = flow_mean

    # 3) RANSAC 필터
    in_prev, in_next, F, mask = ransac_filter(
        prev_valid, next_valid,
        threshold=1.0,
        prob=0.999,
        frame_shape=frame.shape,
        grid_size=(8, 6),
        dir_cos_thresh=0.5,
        sigma_scale=2.0
    )

    if mask is None:
        in_prev = prev_valid
        in_next = next_valid
        ransac_ratio = 0.0
    else:
        ransac_ratio = (np.count_nonzero(mask) / len(mask)) * 100.0

    # 4) Essential 기반 size 계산
    R, t, size, stats = estimate_motion(in_prev, in_next, K)

    if stats["pose_ok"]:
        # size는 비율값이므로 multiplicative update가 적절함
        target = max(0.5, min(2.0, size))  # 안전 범위
        size_acc = size_acc * (0.9 + 0.1 * target)

        # 전체 pose 누적
        R_total = R @ R_total
        t_total = t_total + (R_total @ t)

    # 5) 특징점 보충
    if len(in_next) < 300:
        new_pts, _ = extract_features(gray)
        if len(new_pts) > 0:
            prev_pts = np.vstack([in_next, new_pts])
        else:
            prev_pts = in_next
    else:
        prev_pts = in_next

    prev_gray = gray.copy()

    return {
        "tracked": int(len(prev_valid)),
        "inliers": int(len(in_prev)),
        "ransac_ratio": float(ransac_ratio),
        "size": float(size_acc),
        "flow_mean": (float(flow_mean[0]), float(flow_mean[1])),
    }


# ==========================================================
# 🔧 기존 (x, y, z) 좌표를 Optical Flow + Size 기반으로 갱신
# ==========================================================
def update_existing_xyz(x, y, z):
    """
    기존 AR Marker의 (x,y,z)를
    Optical Flow 이동량 + Essential 기반 size로 업데이트
    """
    global last_flow_mean, size_acc

    dx, dy = last_flow_mean

    x_new = x - dx
    y_new = y - dy
    z_new = z * size_acc

    return float(x_new), float(y_new), float(z_new)
