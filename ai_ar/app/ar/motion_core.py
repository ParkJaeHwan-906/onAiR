import numpy as np
import cv2
import os
from app.sockets.socket_manager import sio  # ✅ Socket.IO 가져오기
from app.ar.feature_extractor import extract_features
from app.ar.feature_tracker import track_features
from app.ar.ransac_filter import ransac_filter
from app.ar.motion_estimator import estimate_motion

# --- 전역 상태 ---
K_global = None
prev_gray = None
prev_pts = None
R_total = np.eye(3, dtype=np.float32)
t_total = np.zeros((3, 1), dtype=np.float32)
last_inlier_old = None
last_inlier_new = None
frame_idx = 0

# --- 파라미터 ---
SCALE_FACTOR = 0.3
REVERSE_T = True
MIN_TRACKS = 60


def init_calibration(path="../data/camera_intrinsics.npy"):
    """카메라 내부 파라미터 로드"""
    global K_global
    K_global = np.load(path) if os.path.exists(path) else None
    print("✅ Camera intrinsics loaded." if K_global is not None else "⚠️ No intrinsics found.")


async def process_frame(frame, sid=None):
    """프레임 단위 모션 계산 및 x,y,z 송신"""
    global prev_gray, prev_pts, R_total, t_total, last_inlier_old, last_inlier_new, frame_idx

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 초기화 단계
    if prev_gray is None:
        prev_gray = gray
        prev_pts, _ = extract_features(gray)
        return {"status": "init", "features": len(prev_pts)}

    # Optical Flow 추적
    good_prev, good_next, _ = track_features(prev_gray, gray, prev_pts)
    if len(good_prev) < MIN_TRACKS:
        prev_pts, _ = extract_features(gray)
        prev_gray = gray
        return {"status": "few_points", "features": len(prev_pts)}

    # RANSAC 필터
    inlier_prev, inlier_next, _, _ = ransac_filter(good_prev, good_next, K_global)
    if len(inlier_prev) < 8:
        return {"status": "ransac_fail"}

    last_inlier_old = inlier_prev
    last_inlier_new = inlier_next

    # Essential Matrix 기반 Pose 추정
    R, t, E, stats = estimate_motion(inlier_prev, inlier_next, K_global)
    if stats["pose_ok"]:
        R_total = R @ R_total
        step = R_total @ (t * SCALE_FACTOR)
        t_total = t_total - step if REVERSE_T else t_total + step

    # 카메라 위치 계산 (x, y, z)
    cam_pos = (-R_total.T @ t_total).flatten()
    x, y, z = cam_pos.tolist()

    # 업데이트
    prev_gray = gray
    prev_pts = good_next.reshape(-1, 1, 2)
    frame_idx += 1

    # ✅ 클라이언트로 실시간 송신
    if sid is not None:
        await sio.emit("camera-position", {"x": x, "y": y, "z": z}, to=sid)

    # 결과 반환
    return {
        "status": "ok",
        "frame_idx": frame_idx,
        "inliers": len(inlier_prev),
        "t": t_total.flatten().tolist(),
        "R": R_total.flatten().tolist(),
        "x": x,
        "y": y,
        "z": z
    }
