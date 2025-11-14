import cv2
import numpy as np


# ==========================================================
# 🔧 미리 생성해두는 전역 객체 (재사용 → 성능 + 안정성 ↑)
# ==========================================================
_CLAHE = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))

_ORB = cv2.ORB_create(
    nfeatures=1200,
    scaleFactor=1.2,
    nlevels=8,
    edgeThreshold=15,
    patchSize=31,
)


# ==========================================================
# 🔧 전역 거리 기반 NMS (셀 경계 중복 제거)
# ==========================================================
def _nms_distance(points: np.ndarray, min_dist: float) -> np.ndarray:
    if len(points) == 0:
        return points

    pts = points.reshape(-1, 2)
    keep = []
    taken = np.zeros(len(pts), dtype=bool)

    for i in range(len(pts)):
        if taken[i]:
            continue
        keep.append(i)

        diff = pts - pts[i]
        dist2 = diff[:, 0]**2 + diff[:, 1]**2
        mask = dist2 < (min_dist * min_dist)
        taken[mask] = True

    kept = pts[keep].reshape(-1, 1, 2)
    return kept.astype(np.float32)


# ==========================================================
# 🔧 균등 GFTT
# ==========================================================
def _extract_features_uniform_gftt(
    gray: np.ndarray,
    *,
    grid_rows=6,
    grid_cols=8,
    max_per_cell=25,
    quality_level=0.05,
    min_distance=8,
    block_size=7,
    do_subpixel=True,
    border=8
):
    h, w = gray.shape[:2]
    cell_h, cell_w = h // grid_rows, w // grid_cols
    all_points = []

    for r in range(grid_rows):
        for c in range(grid_cols):

            y1 = max(r * cell_h, border)
            y2 = min((r + 1) * cell_h, h - border) if r < grid_rows - 1 else h - border

            x1 = max(c * cell_w, border)
            x2 = min((c + 1) * cell_w, w - border) if c < grid_cols - 1 else w - border

            roi = gray[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            pts = cv2.goodFeaturesToTrack(
                roi,
                maxCorners=max_per_cell,
                qualityLevel=quality_level,
                minDistance=min_distance,
                blockSize=block_size
            )

            if pts is not None:
                pts[:, 0, 0] += x1
                pts[:, 0, 1] += y1
                all_points.append(pts)

    if not all_points:
        return np.array([]), "GFTT-Uniform"

    points = np.vstack(all_points).astype(np.float32)

    # 셀 경계 전역 NMS
    points = _nms_distance(points, min_distance)

    # Subpixel refinement
    if do_subpixel and len(points) > 0:
        cv2.cornerSubPix(
            gray, points,
            winSize=(5, 5),
            zeroZone=(-1, -1),
            criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )

    return points, "GFTT-Uniform"


# ==========================================================
# 🔧 균등 ORB (저대비 폴백 → 균등 분포 유지)
# ==========================================================
def _extract_features_uniform_orb(
    gray: np.ndarray,
    grid_rows=6,
    grid_cols=8,
    max_per_cell=25,
    border=8
):
    h, w = gray.shape[:2]
    cell_h, cell_w = h // grid_rows, w // grid_cols

    all_points = []

    for r in range(grid_rows):
        for c in range(grid_cols):
            y1 = max(r * cell_h, border)
            y2 = min((r + 1) * cell_h, h - border)

            x1 = max(c * cell_w, border)
            x2 = min((c + 1) * cell_w, w - border)

            roi = gray[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            keypoints = _ORB.detect(roi, None)
            if not keypoints:
                continue

            pts = np.array([kp.pt for kp in keypoints], dtype=np.float32).reshape(-1, 1, 2)
            pts[:, 0, 0] += x1
            pts[:, 0, 1] += y1
            all_points.append(pts)

    if not all_points:
        return np.array([]), "ORB-Uniform"

    points = np.vstack(all_points).astype(np.float32)
    return points, "ORB-Uniform"


# ==========================================================
# 🎯 최종 통합 특징점 추출기
# ==========================================================
def extract_features(
    gray_frame: np.ndarray,
    *,
    max_corners=1200,
    base_quality=0.05,
    base_min_dist=8
):
    if gray_frame is None or gray_frame.size == 0:
        return np.array([]), "NONE"

    # 미리 생성한 CLAHE로 보정
    enhanced = _CLAHE.apply(gray_frame)

    # Laplacian variance → 텍스처 판단
    lap_var = cv2.Laplacian(enhanced, cv2.CV_64F).var()

    # ============================
    # 1) 고대비 지역 (라플라시안 > 25)
    # ============================
    if lap_var > 25.0:
        points, method = _extract_features_uniform_gftt(
            enhanced,
            grid_rows=6,
            grid_cols=8,
            max_per_cell=30,
            quality_level=base_quality,
            min_distance=base_min_dist,
            block_size=7,
            do_subpixel=True
        )
        return points, method

    # ============================
    # 2) 중간 대비 (10 ≤ Var ≤ 25) → GFTT 강화 버전
    # ============================
    elif lap_var >= 10.0:
        points, method = _extract_features_uniform_gftt(
            enhanced,
            grid_rows=6,
            grid_cols=8,
            max_per_cell=35,
            quality_level=base_quality * 0.7,
            min_distance=max(base_min_dist - 2, 5),
            block_size=5,
            do_subpixel=True
        )
        return points, method

    # ============================
    # 3) 저대비 (Var < 10) → ORB 균등 폴백
    # ============================
    else:
        points = _extract_features_uniform_orb(
            enhanced,
            grid_rows=6,
            grid_cols=8,
            max_per_cell=max_corners // (6 * 8),
        )
        print(f"⚠️ Low contrast (Var={lap_var:.2f}) → ORB-Uniform ({len(points)} pts)")
        return points, "ORB-Uniform"
