# 📄 anchor_manager.py
import numpy as np

Z_ALPHA = 50.0
Z_MIN, Z_MAX = 0.1, 10.0
_anchors = []
_next_id = 0


def add_anchor(x, y, last_inlier_old, last_inlier_new, K, R_total, t_total):
    """
    클릭한 (x,y)에 대한 3D world 좌표를 계산
    Returns: {"id": int, "world": [X,Y,Z], "z": float}
    """
    global _anchors, _next_id

    if (
        K is None
        or last_inlier_old is None
        or last_inlier_new is None
        or len(last_inlier_old) < 8
    ):
        z = 1.0  # fallback
    else:
        pts_old = last_inlier_old.reshape(-1, 2)
        pts_new = last_inlier_new.reshape(-1, 2)

        # 클릭 위치와 가장 가까운 optical flow 벡터 탐색
        d2 = np.sum((pts_old - np.array([x, y], dtype=np.float32))**2, axis=1)
        idx = int(np.argmin(d2))
        flow_vec = pts_new[idx] - pts_old[idx]
        flow_len = float(np.linalg.norm(flow_vec))

        fx, fy = K[0, 0], K[1, 1]
        f = (fx + fy) / 2.0
        z = (Z_ALPHA * (f / 1000.0)) / (flow_len + 1e-3)
        z = float(np.clip(z, Z_MIN, Z_MAX * 3))

    # === 3D world 좌표 계산 ===
    pixel_h = np.array([[x], [y], [1.0]], dtype=np.float32)
    cam_ray = np.linalg.inv(K) @ pixel_h * z      # 카메라 좌표계 점
    world_point = np.linalg.inv(R_total) @ (cam_ray - t_total)  # 월드 좌표계 변환

    anchor = {
        "id": _next_id,
        "x": float(world_point[0]),
        "y": float(world_point[1]),
        "z": float(world_point[2]),
        "depth": z,
    }
    _anchors.append(anchor)
    _next_id += 1
    print(f"📍 Added anchor #{anchor['id']}: {anchor}")
    return anchor


def get_anchors():
    """현재 등록된 모든 앵커 반환"""
    return _anchors
