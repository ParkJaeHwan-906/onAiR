import os
import cv2
import numpy as np

# ============================
# 🔧 파라미터 (기존 값 유지)
# ============================
MIN_FEATURES = 50
MIN_DIST_BETWEEN = 10.0
MAX_AGE = 30

# intrinsics 로드
def _load_K():
    # app/ar/motion_core.py 기준 ../data/K.npy
    here = os.path.dirname(__file__)
    k_path = os.path.join(here, "..", "data", "K.npy")
    if os.path.exists(k_path):
        return np.load(k_path).astype(np.float32)
    # fallback (640x480 가정)
    fx, fy, cx, cy = 800, 800, 320, 240
    return np.array([[fx, 0, cx],
                     [0, fy, cy],
                     [0, 0, 1]], dtype=np.float32)

# ============================
# 🔁 전역 상태
# ============================
K = _load_K()

prev_gray = None
frame_idx = 0

R_total = np.eye(3, dtype=np.float32)
t_total = np.zeros((3, 1), dtype=np.float32)

feature_pool = {
    "pts": np.empty((0, 1, 2), dtype=np.float32),
    "age": np.empty((0,), dtype=np.int32)
}

# === 상대 size 계산을 위한 최신 인라이어/시차 캐시 ===
last_inlier_prev = None   # (N,2)
last_inlier_next = None   # (N,2)
last_parallax = None      # (N,)
last_parallax_med = 1.0   # 전역 기준용 (0 방지 위해 1.0 기본값)

# ============================
# 📦 외부 의존
# ============================
from app.ar.feature_extractor import extract_features
from app.ar.feature_tracker import track_features
from app.ar.ransac_filter import ransac_filter
from app.ar.motion_estimator import estimate_motion

def get_pose():
    """현재 누적 포즈 반환 (R_total, t_total) 복사본"""
    return R_total.copy(), t_total.copy()


def reset_pose(hard=False):
    """
    포즈/상태 초기화.
    - hard=True: prev_gray/feature_pool 포함 전부 리셋
    - hard=False: 누적 포즈만 리셋
    """
    global R_total, t_total, prev_gray, frame_idx, feature_pool
    global last_inlier_prev, last_inlier_next, last_parallax, last_parallax_med

    R_total = np.eye(3, dtype=np.float32)
    t_total = np.zeros((3, 1), dtype=np.float32)
    last_inlier_prev = None
    last_inlier_next = None
    last_parallax = None
    last_parallax_med = 1.0

    if hard:
        prev_gray = None
        frame_idx = 0
        feature_pool = {
            "pts": np.empty((0, 1, 2), dtype=np.float32),
            "age": np.empty((0,), dtype=np.int32)
        }


def _maintain_feature_pool(gray, prev_valid, next_valid):
    """기존 로직 그대로 점 풀 유지/보강"""
    global feature_pool

    # === 점 관리 ===
    if len(next_valid) > 0:
        feature_pool["pts"] = next_valid
        feature_pool["age"] = np.zeros(len(next_valid), dtype=np.int32)
    else:
        if feature_pool["age"].size > 0:
            feature_pool["age"] += 1

    if feature_pool["age"].size > 0:
        valid_mask = feature_pool["age"] < MAX_AGE
        feature_pool["pts"] = feature_pool["pts"][valid_mask]
        feature_pool["age"] = feature_pool["age"][valid_mask]

    # 부족하면 채움
    if len(feature_pool["pts"]) < MIN_FEATURES:
        new_pts, _ = extract_features(gray)
        if new_pts is not None and len(new_pts) > 0:
            if len(feature_pool["pts"]) > 0:
                dist = np.linalg.norm(
                    new_pts.reshape(-1, 1, 2) - feature_pool["pts"].reshape(1, -1, 2),
                    axis=2
                )
                mask_far = (dist.min(axis=1) > MIN_DIST_BETWEEN)
                added_pts = new_pts[mask_far]
            else:
                added_pts = new_pts

            if len(added_pts) > 0:
                feature_pool["pts"] = np.vstack((feature_pool["pts"], added_pts))
                ages = np.full(len(added_pts), -MAX_AGE, dtype=np.int32)
                if feature_pool["age"].size == 0:
                    feature_pool["age"] = ages
                else:
                    feature_pool["age"] = np.concatenate((feature_pool["age"], ages))


async def process_frame(frame_bgr, sid=None):
    """
    ✅ 단일 프레임 입력 → OpticalFlow → RANSAC(F) → Essential → 누적 R,t 업데이트
    반환:
      {
        "status": "init" | "ok" | "skip",
        "x": float, "y": float, "z": float,           # 카메라 월드 좌표 (t_total)
        "inliers": int, "scale": float,
        "parallax_mean": float, "parallax_med": float,
        "relative_depth_global": float,               # = 1 / (parallax_med + eps)
        "R_total": np.ndarray(3x3), "t_total": np.ndarray(3x1)
      }
    """
    global prev_gray, frame_idx, R_total, t_total, feature_pool, K
    global last_inlier_prev, last_inlier_next, last_parallax, last_parallax_med

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    # 초기 프레임: 특징점 초기화
    if prev_gray is None:
        init_pts, _ = extract_features(gray)
        if init_pts is not None and len(init_pts) > 0:
            feature_pool["pts"] = init_pts
            feature_pool["age"] = np.zeros(len(init_pts), dtype=np.int32)
        prev_gray = gray.copy()
        frame_idx += 1
        return {
            "status": "init",
            "x": float(t_total[0]), "y": float(t_total[1]), "z": float(t_total[2]),
            "inliers": 0, "scale": 1.0,
            "parallax_mean": 0.0, "parallax_med": 0.0,
            "relative_depth_global": 0.0,
            "R_total": R_total.copy(), "t_total": t_total.copy()
        }

    # 이전 프레임의 특징점
    prev_pts = feature_pool["pts"]

    # === Optical Flow ===
    prev_valid, next_valid, _ = track_features(
        prev_gray, gray, prev_pts,
        fb_thresh=1.5,
        large_motion_px=100.0,
        enable_equalize=False,
        blur_var_thresh=12.0,
        lk_win_size=(25, 25),
        lk_max_level=4,
        frame=None
    )

    # 점 풀 유지/보강
    _maintain_feature_pool(gray, prev_valid, next_valid)

    # === RANSAC + Essential ===
    status = "skip"
    inliers = 0
    scale = 1.0
    parallax_mean = 0.0
    parallax_med = last_parallax_med  # 직전값 fallback

    if len(prev_valid) >= 8 and len(next_valid) >= 8:
        inlier_prev, inlier_next, F, inlier_mask = ransac_filter(
            prev_valid, next_valid, threshold=1.0, prob=0.999, visualize=False
        )

        if inlier_mask is not None:
            inliers = int(np.count_nonzero(inlier_mask))

            if inliers >= 8:
                # === 시차 통계 계산 (상대 size 근거) ===
                parallax = np.linalg.norm(inlier_next - inlier_prev, axis=1)  # (N,)
                parallax_mean = float(np.mean(parallax))
                parallax_med = float(np.median(parallax)) if parallax.size > 0 else last_parallax_med
                if parallax_med <= 1e-9:
                    parallax_med = 1e-6

                # 캐시 갱신
                last_inlier_prev = inlier_prev.copy()
                last_inlier_next = inlier_next.copy()
                last_parallax = parallax.copy()
                last_parallax_med = parallax_med

                # === Essential 기반 모션 ===
                R, t, E, stats = estimate_motion(inlier_prev, inlier_next, K)
                if stats.get("pose_ok", False):
                    scale = float(stats.get("scale", 1.0))
                    # 누적 포즈 갱신: t_total = t_total + R_total@(s*t), R_total = R @ R_total
                    t_total += R_total @ (scale * t)
                    R_total = R @ R_total
                    status = "ok"

    prev_gray = gray.copy()
    frame_idx += 1

    relative_depth_global = 1.0 / (parallax_med + 1e-6)  # 전역 기준(작을수록 멀리)

    return {
        "status": status,
        "x": float(t_total[0]), "y": float(t_total[1]), "z": float(t_total[2]),
        "inliers": inliers, "scale": scale,
        "parallax_mean": parallax_mean, "parallax_med": parallax_med,
        "relative_depth_global": float(relative_depth_global),
        "R_total": R_total.copy(), "t_total": t_total.copy()
    }


# ============================
# 📐 픽셀 → 월드(z=const 평면) 변환 (선택)
# ============================
def pixel_to_world_on_plane(u, v, plane_z=0.0):
    """
    현재 포즈(R_total,t_total)와 K를 사용해, 이미지 픽셀(u,v)의 광선을
    월드 z=plane_z 평면과 교차시켜 3D 좌표를 구함.
    반환: (x,y,z) or None
    """
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    x_cam = (u - cx) / fx
    y_cam = (v - cy) / fy
    dir_cam = np.array([x_cam, y_cam, 1.0], dtype=np.float32).reshape(3, 1)

    # world 방향
    dir_world = R_total @ dir_cam
    dir_world = dir_world.reshape(3)

    C = t_total.reshape(3)
    denom = dir_world[2]
    if abs(denom) < 1e-8:
        return None
    t = (plane_z - C[2]) / denom
    if t <= 0:
        return None
    P = C + t * dir_world
    return (float(P[0]), float(P[1]), float(P[2]))


# ============================
# 🧩 상대적 size 헬퍼
# ============================
def _knn_local_parallax(u, v, k=5):
    """
    (u,v) 근방의 인라이어에 기반하여 국소 시차(중앙값)를 추정.
    캐시가 없거나 근방 인라이어가 없으면 None.
    """
    global last_inlier_prev, last_parallax
    if last_inlier_prev is None or last_parallax is None or last_inlier_prev.shape[0] == 0:
        return None

    pts = last_inlier_prev  # (N,2), 이전 프레임 좌표 기준
    diffs = pts - np.array([u, v], dtype=np.float32)
    d2 = np.sum(diffs * diffs, axis=1)  # 제곱거리
    order = np.argsort(d2)
    kk = min(k, pts.shape[0])
    sel = order[:kk]
    local_parallax = np.median(last_parallax[sel]) if kk > 0 else None
    return float(local_parallax) if local_parallax is not None else None


def relative_size_at(u, v, k=5):
    """
    단일 픽셀(u,v)에 대한 상대적 size 값.
    정의: global_median_parallax / local_parallax
    - 값이 클수록 '가깝다/커 보인다'
    """
    global last_parallax_med
    local = _knn_local_parallax(u, v, k=k)
    if local is None or local <= 1e-9:
        return None
    return float(last_parallax_med / (local + 1e-6))


def relative_size_in_bbox(x0, y0, x1, y1):
    """
    bbox 내부 인라이어 기반의 상대적 size.
    - 입력: 좌상(x0,y0), 우하(x1,y1)
    - 반환: relative_size (float) or None
    """
    global last_inlier_prev, last_parallax, last_parallax_med
    if last_inlier_prev is None or last_parallax is None:
        return None

    x_min, x_max = min(x0, x1), max(x0, x1)
    y_min, y_max = min(y0, y1), max(y0, y1)

    pts = last_inlier_prev  # (N,2)
    mask = (pts[:, 0] >= x_min) & (pts[:, 0] <= x_max) & (pts[:, 1] >= y_min) & (pts[:, 1] <= y_max)
    if not np.any(mask):
        return None

    local_med = float(np.median(last_parallax[mask]))
    if local_med <= 1e-9:
        return None
    return float(last_parallax_med / (local_med + 1e-6))
