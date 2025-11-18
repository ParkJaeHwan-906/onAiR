# motion_core.py
# ------------------------------------------------------------
# 📌 Optical Flow + RANSAC + Essential 기반
# 📌 AR Marker UI 이동(x,y) + Size(z) 계산
# ------------------------------------------------------------

import numpy as np
import cv2
import os

from .feature_extractor import extract_features
from .feature_tracker import track_features
from .ransac_filter import ransac_filter
from .motion_estimator import estimate_motion


# ==========================================================
# 🎯 설정 (카메라 파라미터 파일 경로)
# ==========================================================
INTR_PATH = "../data/camera_intrinsics.npy"
DIST_PATH = "../data/dist_coeffs.npy"


# ==========================================================
# 🔧 전역 상태 (스트리밍 동안 유지)
# ==========================================================
K: np.ndarray | None = None
D: np.ndarray | None = None

prev_gray: np.ndarray | None = None
prev_pts: np.ndarray | None = None

# 카메라 전체 pose (필요하면 사용)
R_total = np.eye(3, dtype=np.float32)
t_total = np.zeros((3, 1), dtype=np.float32)

# Essential 기반 size(=z proxy) 누적값
size_acc = 1.0

# Optical Flow 평균 이동량 (dx, dy)
last_flow_mean = np.array([0.0, 0.0], dtype=np.float32)


# ==========================================================
# 🔧 카메라 파라미터 로드 (파일 기반 기본값)
# ==========================================================
def load_camera_params():
    """camera_intrinsics.npy / dist_coeffs.npy 에서 K, D 를 로드 (없으면 기본값)."""
    if os.path.exists(INTR_PATH):
        K_local = np.load(INTR_PATH).astype(np.float32)
        # print("📌 [motion_core] Loaded K from camera_intrinsics.npy")
    else:
        # print("⚠️ [motion_core] camera_intrinsics.npy 없음 → 기본 K 사용")
        K_local = np.array([[800, 0, 320],
                            [0, 800, 240],
                            [0,   0,   1]], dtype=np.float32)

    if os.path.exists(DIST_PATH):
        D_local = np.load(DIST_PATH).astype(np.float32)
        # print("📌 [motion_core] Loaded distortion coeffs from dist_coeffs.npy")
    else:
        # print("⚠️ [motion_core] dist_coeffs.npy 없음 → 왜곡 보정 없이 진행")
        D_local = None

    return K_local, D_local


# ==========================================================
# 🔧 초기화 함수 (서버 시작 시 1회 호출 권장)
#   - K_in, D_in 을 직접 넘기면 그걸 사용
#   - 안 넘기면 load_camera_params() 로 파일에서 로드
# ==========================================================
def init(K_in: np.ndarray | None = None, D_in: np.ndarray | None = None):
    global K, D, prev_gray, prev_pts, R_total, t_total, size_acc, last_flow_mean

    if K_in is not None:
        K = K_in.astype(np.float32)
        D = D_in.astype(np.float32) if D_in is not None else None
        # print("📌 [motion_core] Initialized with external K/D")
    else:
        K_loaded, D_loaded = load_camera_params()
        K = K_loaded
        D = D_loaded
        # print("📌 [motion_core] Initialized with loaded K/D")

    # 상태 초기화
    prev_gray = None
    prev_pts = None
    R_total = np.eye(3, dtype=np.float32)
    t_total = np.zeros((3, 1), dtype=np.float32)
    size_acc = 1.0
    last_flow_mean = np.array([0.0, 0.0], dtype=np.float32)

    # print("✅ [motion_core] 초기화 완료")


# ==========================================================
# 🔧 prev_pts / pts 정규화 유틸 (feature_tracker와 동일한 안정판)
# ==========================================================
def _normalize_points_to_n12(pts):
    if pts is None:
        return None

    try:
        if isinstance(pts, (list, tuple)) and len(pts) > 0 \
            and isinstance(pts[0], (np.ndarray, list, tuple)):

            parts = []
            for p in pts:
                if p is None:
                    continue
                a = np.asarray(p, dtype=np.float32)

                if a.ndim == 1:
                    if a.size < 2:
                        continue
                    a = a[:2].reshape(1, 1, 2)
                elif a.ndim == 2:
                    if a.shape[1] < 2:
                        continue
                    a = a[:, :2].reshape(-1, 1, 2)
                elif a.ndim >= 3:
                    if a.shape[-1] < 2:
                        continue
                    a = a[..., :2].reshape(-1, 1, 2)

                if len(a) > 0:
                    parts.append(a)

            if not parts:
                return None

            pts_arr = np.vstack(parts)

        else:
            pts_arr = np.asarray(pts, dtype=np.float32)

        if pts_arr.ndim == 1:
            if pts_arr.size < 2:
                return None
            pts_arr = pts_arr[:2].reshape(1, 1, 2)

        elif pts_arr.ndim == 2:
            if pts_arr.shape[1] < 2:
                return None
            pts_arr = pts_arr[:, :2].reshape(-1, 1, 2)

        elif pts_arr.ndim >= 3:
            if pts_arr.shape[-1] < 2:
                return None
            pts_arr = pts_arr[..., :2].reshape(-1, 1, 2)

        if len(pts_arr) == 0:
            return None

        return pts_arr.astype(np.float32)

    except ValueError:
        return None

# ==========================================================
# 🔧 Optical Flow 평균 이동 계산
# ==========================================================
def compute_flow_mean(prev_pts, next_pts):
    if prev_pts is None or len(prev_pts) == 0:
        return np.array([0.0, 0.0], dtype=np.float32)

    p1 = prev_pts.reshape(-1, 2)
    p2 = next_pts.reshape(-1, 2)
    flow = p2 - p1
    return np.mean(flow, axis=0).astype(np.float32)


# ==========================================================
# 🔧 클릭된 marker 좌표 업데이트
#    Optical Flow 기반 UI 이동 + Essential size 기반 크기
#    (x,y 는 Optical Flow 로, size(z proxy)는 Essential Matrix 로)
# ==========================================================
def update_marker_position(u, v):
    """
    입력: 화면 픽셀 좌표 (u, v)
    출력: (u_new, v_new, size)  - size 는 z 방향 스케일 proxy
    """
    global last_flow_mean, size_acc

    dx, dy = last_flow_mean

    # ✅ Optical Flow 방향과 같이 움직이도록 (+) 로 바꾼다
    u_new = float(u) + float(dx)
    v_new = float(v) + float(dy)

    size = float(size_acc)

    # print(f"[MARKER] prev=({u:.1f}, {v:.1f}), flow=({dx:.3f},{dy:.3f}) → new=({u_new:.1f}, {v_new:.1f}), size={size:.3f}")

    return u_new, v_new, size


# ==========================================================
# 🔧 기존 (x, y, size) 좌표를 Optical Flow + size 누적값으로 갱신
#    - x,y 는 Optical Flow 로 보정
#    - size 는 누적 size_acc 로 스케일링
# ==========================================================
def update_existing_xyz(x, y, size):
    """
    기존 AR 마커의 UI 좌표(x, y, size)를
    Optical Flow 이동량(dx, dy) + Essential Matrix 기반 size_acc 로 갱신.
    """
    global last_flow_mean, size_acc

    dx, dy = last_flow_mean

    # ✅ 여기서도 - 대신 +
    x_new = float(x) + float(dx)
    y_new = float(y) + float(dy)
    size_new = float(size) * float(size_acc)

    return x_new, y_new, size_new


# ==========================================================
# 🔧 프레임 처리 (스트리밍 메인 함수)
#   - socket_handler 에서 매 프레임마다 호출
#   - return dict:
#       {
#         "status": "init" | "ok" | "no_tracks" | "error",
#         "tracked": int,
#         "inliers": int,
#         "ransac_ratio": float,
#         "size": float,
#         "flow_mean": (dx, dy),
#         "pose_ok": bool
#       }
# ==========================================================
def process_frame(frame_bgr, sid=None):
    global K, D
    global prev_gray, prev_pts
    global last_flow_mean, size_acc
    global R_total, t_total

    # --- 0) K 미설정 상태면 안전하게 로드 ---
    if K is None:
        # print("⚠️ [motion_core] K is None → load_camera_params() 호출")
        K_local, D_local = load_camera_params()
        K = K_local
        D = D_local

    # --- 1) Undistort ---
    if D is not None:
        frame = cv2.undistort(frame_bgr, K, D)
    else:
        frame = frame_bgr

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # --- 2) 첫 프레임: 특징점만 추출 ---
    if prev_gray is None:
        # print("[DEBUG] [STEP1] 첫 번째 프레임 - 특징점 추출")
        pts, method = extract_features(gray)
        if pts is None:
            # print("[DEBUG]  ▶ 특징점 0개 (None) → 빈 배열로 대체")
            pts = np.empty((0, 1, 2), dtype=np.float32)
        # print(f"[DEBUG]  ▶ 특징점 추출 방법: {method}, 개수: {len(pts)}")

        prev_gray = gray.copy()
        prev_pts = pts

        # 초기 상태 리포트
        return {
            "status": "init",
            "tracked": int(len(pts)),
            "inliers": int(len(pts)),
            "ransac_ratio": 100.0 if len(pts) > 0 else 0.0,
            "size": float(size_acc),
            "flow_mean": (0.0, 0.0),
            "pose_ok": False,
        }

    # --- 3) Optical Flow 추적 ---
    # print("[DEBUG] [STEP2] Optical Flow 추적 시작")
    # print(f"[DEBUG]  ▶ 입력 특징점 수: {0 if prev_pts is None else len(prev_pts)}")

    prev_valid, next_valid, _ = track_features(
        prev_gray,
        gray,
        prev_pts,
        fb_thresh=2.0,
        blur_var_thresh=12.0,
        lk_win_size=(25, 25),
        lk_max_level=4,
        frame=frame,
    )

    # if prev_valid is None:
    #     print("[DEBUG]  ▶ Optical Flow 결과: prev_valid=None")
    # else:
    #     print(f"[DEBUG]  ▶ Optical Flow 유효 포인트 수: {len(prev_valid)}")

    # ---- Optical Flow 실패 시: 즉시 재초기화 시도 ----
    if prev_valid is None or len(prev_valid) == 0:
        # print("[DEBUG]  ▶ Optical Flow 추적 실패 → 특징점 재추출 시도")
        pts, method = extract_features(gray)

        if pts is None or len(pts) == 0:
            # print("[DEBUG]  ▶ 재추출도 실패 → no_tracks 상태 반환")
            prev_gray = gray.copy()
            prev_pts = None
            last_flow_mean = np.array([0.0, 0.0], dtype=np.float32)
            return {
                "status": "no_tracks",
                "tracked": 0,
                "inliers": 0,
                "ransac_ratio": 0.0,
                "size": float(size_acc),
                "flow_mean": (0.0, 0.0),
                "pose_ok": False,
            }

        # 재추출 성공 → init 상태로 복귀
        # print(f"[DEBUG]  ▶ 재추출 성공: {method}, 특징점 {len(pts)}개")
        if prev_valid is not None and len(prev_valid) > 0:
            prev_pts = np.vstack([prev_valid, pts])
        else:
            prev_pts = pts

        prev_gray = gray.copy()
        last_flow_mean = np.array([0.0, 0.0], dtype=np.float32)

        return {
            "status": "init",
            "tracked": int(len(pts)),
            "inliers": int(len(pts)),
            "ransac_ratio": 100.0 if len(pts) > 0 else 0.0,
            "size": float(size_acc),
            "flow_mean": (0.0, 0.0),
            "pose_ok": False,
        }

    # Optical Flow 평균 이동량
    flow_mean = compute_flow_mean(prev_valid, next_valid)
    last_flow_mean = flow_mean
    # print(f"[DEBUG]  ▶ Optical Flow 평균 이동량: dx={flow_mean[0]:.3f}, dy={flow_mean[1]:.3f}")

    # --- 4) RANSAC 필터링 ---
    # print("[DEBUG] [STEP3] RANSAC 필터링 시작")
    in_prev, in_next, F, mask = ransac_filter(
        prev_valid,
        next_valid,
        threshold=1.0,
        prob=0.999,
        frame_shape=frame.shape,
        grid_size=(8, 6),
        dir_cos_thresh=0.5,
        sigma_scale=2.0,
    )

    if mask is not None:
        inlier_count = int(np.count_nonzero(mask))
        total = len(mask)
        ransac_ratio = (inlier_count / total) * 100.0 if total > 0 else 0.0
        # print(f"[DEBUG]  ▶ RANSAC 결과: inliers={inlier_count}/{total} ({ransac_ratio:.1f}%)")
    else:
        # RANSAC 실패 시 전체를 inlier 로 사용
        # print("[DEBUG]  ▶ RANSAC 실패 → 모든 포인트를 inlier로 사용")
        in_prev = prev_valid
        in_next = next_valid
        inlier_count = len(in_prev)
        total = len(in_prev)
        ransac_ratio = 0.0

    # --- 5) Essential 기반 Motion 추정 (size = z proxy) ---
    # print("[DEBUG] [STEP4] Essential 기반 Motion 추정 시작")
    pose_ok = False
    try:
        # print(f"[DEBUG]  ▶ estimate_motion 입력 포인트 수: {len(in_prev)}")
        R, t, size_meas, stats = estimate_motion(in_prev, in_next, K)
        # print(f"[DEBUG]  ▶ estimate_motion 결과: pose_ok={stats.get('pose_ok', False)}, size_meas={size_meas}")

        if stats.get("pose_ok", False):
            pose_ok = True
            # size_meas 를 안정화 / 클램프 후 EMA 누적
            size_clamped = max(0.5, min(2.0, float(size_meas)))
            size_acc_local = 0.9 * float(size_acc) + 0.1 * size_clamped
            size_acc_local = float(size_acc_local)

            # 전역 갱신
            size_acc = size_acc_local
            # print(f"[DEBUG]  ▶ size_acc 업데이트: {size_acc:.4f}")

            # 카메라 전체 pose 누적 (원하면 활용)
            R_total[:] = R @ R_total
            t_total[:] = t_total + (R_total @ t)
        # else:
        #     print("[DEBUG]  ▶ pose_ok=False → size_acc 유지")

    except Exception as e:
        # Essential 계산 실패해도 크래시 나지 않게 보호
        # print(f"⚠️ [motion_core] estimate_motion 실패: {e}")
        pose_ok = False

    # --- 6) 다음 프레임용 특징점 준비 ---
    # print("[DEBUG] [STEP5] 다음 프레임용 특징점 준비")
    if len(in_next) < 300:
        # print(f"[DEBUG]  ▶ in_next={len(in_next)} < 300 → 신규 특징점 추가 추출")
        new_pts, method = extract_features(gray)
        if new_pts is not None and len(new_pts) > 0:
            # print(f"[DEBUG]  ▶ 신규 특징점 {len(new_pts)}개 추가 (method={method})")
            prev_pts = np.vstack([in_next, new_pts])
        else:
            # print("[DEBUG]  ▶ 신규 특징점 추출 실패 → in_next만 사용")
            prev_pts = in_next
    else:
        # print(f"[DEBUG]  ▶ in_next={len(in_next)} ≥ 300 → 그대로 사용")
        prev_pts = in_next

    prev_gray = gray.copy()

    # print(
    #     f"[DEBUG] [RESULT] status=ok, "
    #     f"tracked={len(prev_valid)}, inliers={inlier_count}, "
    #     f"size={size_acc:.4f}, flow_mean=({flow_mean[0]:.3f},{flow_mean[1]:.3f}), "
    #     f"pose_ok={pose_ok}"
    # )

    return {
        "status": "ok",
        "tracked": int(len(prev_valid)),
        "inliers": int(inlier_count),
        "ransac_ratio": float(ransac_ratio),
        "size": float(size_acc),
        "flow_mean": (float(flow_mean[0]), float(flow_mean[1])),
        "pose_ok": pose_ok,
    }


def compute_marker_size(z_scale):
    """
    Essential Matrix 기반 z_scale 값을 UI size(px)로 변환.
    z_scale은 상대 깊이 변화량(1.0=기준).
    """
    base_size = 10.0         # 기준 크기
    scale_factor = 20.0      # 깊이 변화에 따른 확대/축소 정도

    size_px = base_size + (z_scale * scale_factor)

    # 안전 클램프
    return float(np.clip(size_px, 10.0, 120.0))
