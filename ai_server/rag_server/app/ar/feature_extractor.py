# import cv2
# import numpy as np


# # ==========================================================
# # 🎯 균등 분포 GFTT + ORB 폴백 통합 버전
# # ==========================================================
# def _extract_features_uniform_gftt(
#     gray: np.ndarray,
#     *,
#     grid_rows: int = 6,        # [권장 5~8] 세로 분할 개수 (영상 높이 기준)
#     grid_cols: int = 8,        # [권장 6~10] 가로 분할 개수 (영상 폭 기준)
#     max_per_cell: int = 25,    # [권장 30~60] 각 셀당 최대 코너 수 -> 1200 개 max 로 특징점 고정
#     quality_level: float = 0.05,  # [범위 0.01~0.1] 낮을수록 더 많은 코너 검출
#     min_distance: int = 10,        # [범위 3~10 px] 한 셀 내부에서 코너 간 최소 간격
#     block_size: int = 7,          # [범위 3~9] GFTT 윈도우 크기 (주변 블록 크기)
#     do_subpixel: bool = True      # 서브픽셀 정밀화 여부 (True 권장)
# ):
#     """
#     [내부 함수] 균등 분포 GFTT 특징점 추출기
#     ----------------------------------------------------------
#     각 프레임(예: 640x480)을 (grid_rows x grid_cols)로 나누고,
#     각 셀마다 GFTT(goodFeaturesToTrack)를 독립적으로 수행.
#     이렇게 하면 프레임 전체에 특징점이 고르게 분포된다.

#     Args:
#         gray: np.ndarray (H,W), 단일 채널 그레이스케일 영상
#         grid_rows: 세로 분할 수 (예: 6이면 480/6 ≈ 80픽셀 단위로 나눔)
#         grid_cols: 가로 분할 수 (예: 8이면 640/8 ≈ 80픽셀 단위)
#         max_per_cell: 각 셀에서 추출할 최대 특징점 수
#         quality_level: 코너 감도 (작을수록 더 많은 점; 기본 0.08)
#         min_distance: 같은 셀 내에서 포인트 간 최소 거리 (px)
#         block_size: GFTT에서 코너 계산 시 주변 블록 크기 (픽셀 단위)
#         do_subpixel: 서브픽셀 정밀화 수행 여부 (True 시 더 정밀, 약간 느림)

#     Returns:
#         points: (N,1,2) float32 — 전체 프레임 좌표 기준 특징점 리스트
#         method: str — "GFTT-Uniform"
#     ----------------------------------------------------------
#     """

#     h, w = gray.shape[:2]
#     if h == 0 or w == 0:
#         return np.array([]), "GFTT-Uniform"

#     # 셀 크기 계산 (마지막 셀은 약간 작을 수 있음)
#     cell_h, cell_w = h // grid_rows, w // grid_cols
#     all_points = []

#     # === ① 각 셀 단위로 코너 검출 ===
#     for r in range(grid_rows):
#         for c in range(grid_cols):
#             y1, y2 = r * cell_h, (r + 1) * cell_h if r < grid_rows - 1 else h
#             x1, x2 = c * cell_w, (c + 1) * cell_w if c < grid_cols - 1 else w
#             roi = gray[y1:y2, x1:x2]

#             pts = cv2.goodFeaturesToTrack(
#                 roi,
#                 maxCorners=max_per_cell,     # 셀 내부 최대 코너 수
#                 qualityLevel=quality_level,  # 낮을수록 더 민감하게 검출
#                 minDistance=min_distance,    # 중복 방지 간격(px)
#                 blockSize=block_size
#             )

#             if pts is not None:
#                 # 셀 내 좌표 → 전체 프레임 기준 좌표로 보정
#                 pts[:, 0, 0] += x1
#                 pts[:, 0, 1] += y1
#                 all_points.append(pts)

#     if not all_points:
#         return np.array([]), "GFTT-Uniform"

#     # === ② 전체 셀의 결과 병합 ===
#     points = np.vstack(all_points).astype(np.float32)  # (N,1,2)

#     # === ③ Subpixel refinement (정밀 보정) ===
#     if do_subpixel and len(points) > 0:
#         term_crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT, 30, 0.01)
#         cv2.cornerSubPix(gray, points, (5, 5), (-1, -1), term_crit)

#     return points, "GFTT-Uniform"


# # ==========================================================
# # 🎯 최종 통합 특징점 추출 함수
# # ==========================================================
# def extract_features(
#     gray_frame: np.ndarray,
#     max_corners: int = 1200,   # ORB에서 사용되는 최대 특징점 수
#     quality: float = 0.05,     # GFTT의 코너 민감도 (낮을수록 더 많이)
#     min_distance: int = 10      # GFTT 셀 내부 포인트 최소 거리
# ):
#     """
#     ✅ 안정형 특징점 추출기 (GFTT-Uniform ↔ ORB 자동 전환)
#     ----------------------------------------------------------
#     - CLAHE 명암 보정 (조도/역광 대응)
#     - Laplacian variance 기반 명암 평가로 알고리즘 자동 전환:
#         → 충분한 명암 대비 : 균등 분포 GFTT 사용
#         → 저대비 / 평탄 장면 : ORB 폴백
#     - GFTT일 때만 sub-pixel refinement 수행 (고정밀)
#     ----------------------------------------------------------

#     Args:
#         gray_frame: np.ndarray (H,W)
#             단일 채널 그레이스케일 프레임 (640x480 권장)
#         max_corners: int (default=1200)
#             ORB에서 최대 추출할 특징점 개수
#         quality: float (default=0.08)
#             GFTT에서 코너 민감도 (낮을수록 많음)
#         min_distance: int (default=6)
#             같은 셀 내 포인트 간 최소 거리(px)
    
#     Returns:
#         points: np.ndarray (N,1,2), dtype=float32
#             검출된 특징점 좌표 (없으면 빈 배열)
#         method: str
#             "GFTT-Uniform" | "ORB" | "NONE"
#     ----------------------------------------------------------
#     """

#     if gray_frame is None or gray_frame.size == 0:
#         return np.array([]), "NONE"

#     # === ① CLAHE 적용 (조도 및 대비 향상) ===
#     clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
#     enhanced = clahe.apply(gray_frame)

#     # === ② Laplacian variance 계산 ===
#     #     → 장면의 텍스처 / 대비 정도를 정량화 (값이 낮을수록 평탄함)
#     lap_var = cv2.Laplacian(enhanced, cv2.CV_64F).var()
#     low_contrast = lap_var < 10.0  # [경험값] 8~15 사이가 적정, 10이 중간 정도

#     if not low_contrast:
#         # ✅ 충분한 명암 → 균등 분포 GFTT 사용
#         points, method = _extract_features_uniform_gftt(
#             enhanced,
#             grid_rows=4,          # 480/6 ≈ 80px
#             grid_cols=6,          # 640/8 ≈ 80px
#             max_per_cell=30,      # 셀당 최대 코너 수
#             quality_level=quality,
#             min_distance=min_distance,
#             block_size=7,
#             do_subpixel=True
#         )
#         return points, method

#     else:
#         # ⚠️ 저대비 장면 → ORB 폴백
#         orb = cv2.ORB_create(
#             nfeatures=max_corners,  # 전체 프레임에서 최대 특징점 수
#             scaleFactor=1.2,        # 피라미드 스케일 비율 (1.2 권장)
#             nlevels=8,              # 피라미드 레벨 수
#             edgeThreshold=15,       # 영상 경계에서 최소 거리(px)
#             patchSize=31            # 디스크립터 패치 크기 (기본 31)
#         )
#         keypoints = orb.detect(enhanced, None)

#         if not keypoints:
#             return np.array([]), "ORB"

#         points = np.array([kp.pt for kp in keypoints], dtype=np.float32).reshape(-1, 1, 2)
#         print(f"⚠️ Low contrast scene (Var={lap_var:.2f}) — using ORB fallback ({len(points)} pts)")
#         return points.astype(np.float32), "ORB"
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
