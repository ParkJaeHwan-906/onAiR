# import os
# import cv2
# import numpy as np

# # ============================
# # 🔧 파라미터 (기존 값 유지)
# # ============================
# MIN_FEATURES = 50
# MIN_DIST_BETWEEN = 10.0
# MAX_AGE = 30

# # intrinsics 로드
# def _load_K():
#     # app/ar/motion_core.py 기준 ../data/K.npy
#     # here = os.path.dirname(__file__)
#     # k_path = os.path.join(here, "..", "data", "K.npy")
#     # if os.path.exists(k_path):
#     #     return np.load(k_path).astype(np.float32)
#     # fallback (640x480 가정)
#     fx, fy, cx, cy = 942.34, 940.92, 315.93, 223.13
#     return np.array([[fx, 0, cx],
#                      [0, fy, cy],
#                      [0, 0, 1]], dtype=np.float32)

# # ============================
# # 🔁 전역 상태
# # ============================
# K = _load_K()

# prev_gray = None
# frame_idx = 0

# R_total = np.eye(3, dtype=np.float32)
# t_total = np.zeros((3, 1), dtype=np.float32)

# feature_pool = {
#     "pts": np.empty((0, 1, 2), dtype=np.float32),
#     "age": np.empty((0,), dtype=np.int32)
# }

# # === 상대 size 계산을 위한 최신 인라이어/시차 캐시 ===
# last_inlier_prev = None   # (N,2)
# last_inlier_next = None   # (N,2)
# last_parallax = None      # (N,)
# last_parallax_med = 1.0   # 전역 기준용 (0 방지 위해 1.0 기본값)

# # ============================
# # 📦 외부 의존
# # ============================
# from app.ar.feature_extractor import extract_features
# from app.ar.feature_tracker import track_features
# from app.ar.ransac_filter import ransac_filter
# from app.ar.motion_estimator import estimate_motion

# def get_pose():
#     """현재 누적 포즈 반환 (R_total, t_total) 복사본"""
#     return R_total.copy(), t_total.copy()


# def reset_pose(hard=False):
#     """
#     포즈/상태 초기화.
#     - hard=True: prev_gray/feature_pool 포함 전부 리셋
#     - hard=False: 누적 포즈만 리셋
#     """
#     global R_total, t_total, prev_gray, frame_idx, feature_pool
#     global last_inlier_prev, last_inlier_next, last_parallax, last_parallax_med

#     R_total = np.eye(3, dtype=np.float32)
#     t_total = np.zeros((3, 1), dtype=np.float32)
#     last_inlier_prev = None
#     last_inlier_next = None
#     last_parallax = None
#     last_parallax_med = 1.0

#     if hard:
#         prev_gray = None
#         frame_idx = 0
#         feature_pool = {
#             "pts": np.empty((0, 1, 2), dtype=np.float32),
#             "age": np.empty((0,), dtype=np.int32)
#         }


# def _maintain_feature_pool(gray, prev_valid, next_valid):
#     """기존 로직 그대로 점 풀 유지/보강"""
#     global feature_pool

#     # === 점 관리 ===
#     if len(next_valid) > 0:
#         feature_pool["pts"] = next_valid
#         feature_pool["age"] = np.zeros(len(next_valid), dtype=np.int32)
#     else:
#         if feature_pool["age"].size > 0:
#             feature_pool["age"] += 1

#     if feature_pool["age"].size > 0:
#         valid_mask = feature_pool["age"] < MAX_AGE
#         feature_pool["pts"] = feature_pool["pts"][valid_mask]
#         feature_pool["age"] = feature_pool["age"][valid_mask]

#     # 부족하면 채움
#     if len(feature_pool["pts"]) < MIN_FEATURES:
#         new_pts, _ = extract_features(gray)
#         if new_pts is not None and len(new_pts) > 0:
#             if len(feature_pool["pts"]) > 0:
#                 dist = np.linalg.norm(
#                     new_pts.reshape(-1, 1, 2) - feature_pool["pts"].reshape(1, -1, 2),
#                     axis=2
#                 )
#                 mask_far = (dist.min(axis=1) > MIN_DIST_BETWEEN)
#                 added_pts = new_pts[mask_far]
#             else:
#                 added_pts = new_pts

#             if len(added_pts) > 0:
#                 feature_pool["pts"] = np.vstack((feature_pool["pts"], added_pts))
#                 ages = np.full(len(added_pts), -MAX_AGE, dtype=np.int32)
#                 if feature_pool["age"].size == 0:
#                     feature_pool["age"] = ages
#                 else:
#                     feature_pool["age"] = np.concatenate((feature_pool["age"], ages))


# async def process_frame(frame_bgr, sid=None):
#     """
#     ✅ 단일 프레임 입력 → OpticalFlow → RANSAC(F) → Essential → 누적 R,t 업데이트
#     반환:
#       {
#         "status": "init" | "ok" | "skip",
#         "x": float, "y": float, "z": float,           # 카메라 월드 좌표 (t_total)
#         "inliers": int, "scale": float,
#         "parallax_mean": float, "parallax_med": float,
#         "relative_depth_global": float,               # = 1 / (parallax_med + eps)
#         "R_total": np.ndarray(3x3), "t_total": np.ndarray(3x1)
#       }
#     """
#     global prev_gray, frame_idx, R_total, t_total, feature_pool, K
#     global last_inlier_prev, last_inlier_next, last_parallax, last_parallax_med

#     gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
#     _latest_gray = gray.copy()  # 최신 프레임 갱신

#     # 초기 프레임: 특징점 초기화
#     if prev_gray is None:
#         init_pts, _ = extract_features(gray)
#         if init_pts is not None and len(init_pts) > 0:
#             feature_pool["pts"] = init_pts
#             feature_pool["age"] = np.zeros(len(init_pts), dtype=np.int32)
#         prev_gray = gray.copy()
#         frame_idx += 1
#         return {
#             "status": "init",
#             "x": float(t_total[0]), "y": float(t_total[1]), "z": float(t_total[2]),
#             "inliers": 0, "scale": 1.0,
#             "parallax_mean": 0.0, "parallax_med": 0.0,
#             "relative_depth_global": 0.0,
#             "R_total": R_total.copy(), "t_total": t_total.copy()
#         }

#     # 이전 프레임의 특징점
#     prev_pts = feature_pool["pts"]

#     # === Optical Flow ===
#     prev_valid, next_valid, _ = track_features(
#         prev_gray, gray, prev_pts,
#         fb_thresh=1.5,
#         large_motion_px=100.0,
#         enable_equalize=False,
#         blur_var_thresh=12.0,
#         lk_win_size=(25, 25),
#         lk_max_level=4,
#         frame=None
#     )

#     prev_valid_refined = []
#     next_valid_refined = []
#     match_scores = []    
#     patch_hw = 8  # 17x17 템플릿
#     search_r = 12 # 25x25 검색
#     for (x0, y0), (x1, y1) in zip(prev_valid.reshape(-1,2), next_valid.reshape(-1,2)):
#         y0a, y1a = max(0, int(y0 - patch_hw)), min(prev_gray.shape[0], int(y0 + patch_hw + 1))
#         x0a, x1a = max(0, int(x0 - patch_hw)), min(prev_gray.shape[1], int(x0 + patch_hw + 1))
#         tpl = prev_gray[int(y0-patch_hw):int(y0+patch_hw+1),
#                         int(x0-patch_hw):int(x0+patch_hw+1)]
#         if tpl.shape[0] != 2*patch_hw+1 or tpl.shape[1] != 2*patch_hw+1:
#             continue
#         xs0, ys0 = int(x1-search_r), int(y1-search_r)
#         xs1, ys1 = int(x1+search_r+1), int(y1+search_r+1)
#         roi = gray[max(0,ys0):min(gray.shape[0],ys1),
#                 max(0,xs0):min(gray.shape[1],xs1)]
#         if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
#             continue
#         res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
#         _, max_val, _, max_loc = cv2.minMaxLoc(res)
#         match_scores.append(max_val)
#         if max_val >= 0.80:  # 임계값
#             dx, dy = max_loc
#             nx = (max(0,xs0) + dx) + patch_hw
#             ny = (max(0,ys0) + dy) + patch_hw
#             prev_valid_refined.append([x0, y0])
#             next_valid_refined.append([nx, ny])

#     if len(prev_valid_refined) < 8:
#         print(f"⚠️ Too few refined ({len(prev_valid_refined)}), fallback to OF result")
#     else:
#         if match_scores: 
#             mean_score = np.mean(match_scores)
#         else:
#             mean_score = 0.0
#             print(f"✅ Patch refine: {len(prev_valid_refined)} pts | meanNCC={mean_score:.3f}")

#     prev_valid = np.array(prev_valid_refined, dtype=np.float32).reshape(-1,1,2)
#     next_valid = np.array(next_valid_refined, dtype=np.float32).reshape(-1,1,2)

#     # 점 풀 유지/보강
#     _maintain_feature_pool(gray, prev_valid, next_valid)

#     # === RANSAC + Essential ===
#     status = "skip"
#     inliers = 0
#     scale = 1.0
#     parallax_mean = 0.0
#     parallax_med = last_parallax_med  # 직전값 fallback

#     if len(prev_valid) >= 8 and len(next_valid) >= 8:
#         inlier_prev, inlier_next, F, inlier_mask = ransac_filter(
#             prev_valid, next_valid, threshold=1.0, prob=0.999, visualize=False
#         )

#         if inlier_mask is not None:
#             inliers = int(np.count_nonzero(inlier_mask))

#             if inliers >= 8:
#                 # === 시차 통계 계산 (상대 size 근거) ===
#                 parallax = np.linalg.norm(inlier_next - inlier_prev, axis=1)  # (N,)
#                 parallax_mean = float(np.mean(parallax))
#                 parallax_med = float(np.median(parallax)) if parallax.size > 0 else last_parallax_med
#                 if parallax_med <= 1e-9:
#                     parallax_med = 1e-6

#                 # 캐시 갱신
#                 last_inlier_prev = inlier_prev.copy()
#                 last_inlier_next = inlier_next.copy()
#                 last_parallax = parallax.copy()
#                 last_parallax_med = parallax_med

#                 # === Essential 기반 모션 ===
#                 R, t, E, stats = estimate_motion(inlier_prev, inlier_next, K)
#                 if stats.get("pose_ok", False):
#                     scale = float(stats.get("scale", 1.0))
#                     # 누적 포즈 갱신: t_total = t_total + R_total@(s*t), R_total = R @ R_total
#                     t_total += R_total @ (scale * t)
#                     R_total = R @ R_total
#                     status = "ok"

#     prev_gray = gray.copy()
#     frame_idx += 1

#     relative_depth_global = 1.0 / (parallax_med + 1e-6)  # 전역 기준(작을수록 멀리)

#     return {
#         "status": status,
#         "x": float(t_total[0]), "y": float(t_total[1]), "z": float(t_total[2]),
#         "inliers": inliers, "scale": scale,
#         "parallax_mean": parallax_mean, "parallax_med": parallax_med,
#         "relative_depth_global": float(relative_depth_global),
#         "R_total": R_total.copy(), "t_total": t_total.copy()
#     }


# # ============================
# # 📐 픽셀 → 월드(z=const 평면) 변환 (선택)
# # ============================
# def pixel_to_world_on_plane(u, v, plane_z=0.0):
#     """
#     현재 포즈(R_total, t_total)와 K를 사용해 이미지 픽셀(u,v)의 광선을
#     월드 z=plane_z 평면과 교차시켜 3D 좌표를 구함.
#     반환: (x, y, z) or None

#     개선 사항:
#     - 초기 포즈 미설정 시 None 반환
#     - z=0 평면과 평행한 경우 plane_z 자동 보정
#     - 디버그 로그 및 안전한 fallback
#     """
#     global R_total, t_total, K

#     # --- ① 포즈 유효성 검사 ---
#     if np.allclose(t_total, 0, atol=1e-6):
#         print("⚠️ [pixel_to_world_on_plane] Pose not initialized (t_total≈0). Returning None.")
#         return None

#     # --- ② 내참수 추출 ---
#     fx, fy = K[0, 0], K[1, 1]
#     cx, cy = K[0, 2], K[1, 2]

#     # --- ③ 픽셀 → 카메라좌표계 방향벡터 ---
#     x_cam = (u - cx) / fx
#     y_cam = (v - cy) / fy
#     dir_cam = np.array([x_cam, y_cam, 1.0], dtype=np.float32).reshape(3, 1)

#     # --- ④ 카메라→월드 방향 변환 ---
#     dir_world = R_total @ dir_cam
#     dir_world = dir_world.reshape(3)

#     C = t_total.reshape(3)
#     denom = dir_world[2]

#     # --- ⑤ z=0 평면과 평행한 경우 자동 보정 ---
#     if abs(denom) < 1e-8:
#         print("⚠️ [pixel_to_world_on_plane] Ray nearly parallel to plane_z, adjusting plane_z→-1.0")
#         plane_z = -1.0
#         denom = dir_world[2] if abs(dir_world[2]) > 1e-8 else 1e-8

#     # --- ⑥ 평면 교차점 계산 ---
#     t = (plane_z - C[2]) / denom
#     if t <= 0:
#         print(f"⚠️ [pixel_to_world_on_plane] Intersection behind camera (t={t:.4f}) → returning None.")
#         return None

#     P = C + t * dir_world
#     wx, wy, wz = float(P[0]), float(P[1]), float(P[2])

#     # --- ⑦ 디버그 로그 ---
#     # print(f"📍 [pixel_to_world_on_plane] pixel=({u:.1f},{v:.1f}) → world=({wx:.3f},{wy:.3f},{wz:.3f}) | t={t:.3f}")

#     return wx, wy, wz

# # ============================
# # 🧩 상대적 size 헬퍼
# # ============================
# def _knn_local_parallax(u, v, k=5):
#     """
#     (u,v) 근방의 인라이어에 기반하여 국소 시차(중앙값)를 추정.
#     캐시가 없거나 근방 인라이어가 없으면 None.
#     """
#     global last_inlier_prev, last_parallax
#     if last_inlier_prev is None or last_parallax is None or last_inlier_prev.shape[0] == 0:
#         return None

#     pts = last_inlier_prev  # (N,2), 이전 프레임 좌표 기준
#     diffs = pts - np.array([u, v], dtype=np.float32)
#     d2 = np.sum(diffs * diffs, axis=1)  # 제곱거리
#     order = np.argsort(d2)
#     kk = min(k, pts.shape[0])
#     sel = order[:kk]
#     local_parallax = np.median(last_parallax[sel]) if kk > 0 else None
#     return float(local_parallax) if local_parallax is not None else None


# def relative_size_at(u, v, k=5):
#     """
#     단일 픽셀(u,v)에 대한 상대적 size 값.
#     정의: global_median_parallax / local_parallax
#     - 값이 클수록 '가깝다/커 보인다'
#     """
#     global last_parallax_med
#     local = _knn_local_parallax(u, v, k=k)
#     if local is None or local <= 1e-9:
#         return None
#     return float((local + 1e-6) / last_parallax_med)


# def relative_size_in_bbox(x0, y0, x1, y1):
#     """
#     bbox 내부 인라이어 기반의 상대적 size.
#     - 입력: 좌상(x0,y0), 우하(x1,y1)
#     - 반환: relative_size (float) or None
#     """
#     global last_inlier_prev, last_parallax, last_parallax_med
#     if last_inlier_prev is None or last_parallax is None:
#         return None

#     x_min, x_max = min(x0, x1), max(x0, x1)
#     y_min, y_max = min(y0, y1), max(y0, y1)

#     pts = last_inlier_prev  # (N,2)
#     mask = (pts[:, 0] >= x_min) & (pts[:, 0] <= x_max) & (pts[:, 1] >= y_min) & (pts[:, 1] <= y_max)
#     if not np.any(mask):
#         return None

#     local_med = float(np.median(last_parallax[mask]))
#     if local_med <= 1e-9:
#         return None
#     return float(last_parallax_med / (local_med + 1e-6))

# _latest_gray = None  # 전역 캐시

# def get_latest_gray():
#     """가장 최근 프레임의 gray 이미지를 반환"""
#     global _latest_gray
#     return _latest_gray

# def extract_patch_from_current_gray(u, v, half_size=10):
#     """현재 gray 프레임에서 (u,v) 근처 패치를 잘라 반환"""
#     global _latest_gray
#     if _latest_gray is None:
#         return None
#     h, w = _latest_gray.shape
#     u, v = int(u), int(v)
#     x0, y0 = max(0, u - half_size), max(0, v - half_size)
#     x1, y1 = min(w, u + half_size + 1), min(h, v + half_size + 1)
#     patch = _latest_gray[y0:y1, x0:x1]
#     if patch.shape[0] < 2 * half_size or patch.shape[1] < 2 * half_size:
#         return None
#     return patch.copy()

# def refine_patch_position(gray_now, u_pred, v_pred, tpl, search_r=14):
#     """
#     현재 프레임(gray_now)에서 예측좌표(u_pred,v_pred) 근방을 탐색하여
#     템플릿(tpl)과 가장 유사한 위치를 반환.
#     """
#     h, w = gray_now.shape[:2]
#     half_t = tpl.shape[0] // 2
#     x0, y0 = int(u_pred - search_r), int(v_pred - search_r)
#     x1, y1 = int(u_pred + search_r + 1), int(v_pred + search_r + 1)

#     x0c, y0c = max(0, x0), max(0, y0)
#     x1c, y1c = min(w, x1), min(h, y1)
#     roi = gray_now[y0c:y1c, x0c:x1c]

#     if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
#         return (u_pred, v_pred, 0.0)

#     res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
#     _, max_val, _, max_loc = cv2.minMaxLoc(res)
#     if max_val < 0.7:
#         return (u_pred, v_pred, max_val)

#     dx, dy = max_loc
#     u_ref = (x0c + dx) + half_t
#     v_ref = (y0c + dy) + half_t
#     return (float(u_ref), float(v_ref), float(max_val))

# def update_marker_position(marker_u, marker_v, frame_shape=(640,480)):
#     """
#     📍 Optical Flow + Essential Matrix 기반 마커 좌표 업데이트
#     -------------------------------------------------------------
#     이 함수는 클라이언트 뷰파인더(0~968, 0~857) 상의 클릭 좌표 (u,v)를
#     최신 프레임의 카메라 움직임에 맞춰 보정해주는 역할을 한다.

#     입력:
#         marker_u, marker_v : float
#             클라이언트에서 들어온 마커의 초기 클릭 좌표 (뷰파인더 기준)
#         frame_shape : tuple(int, int)
#             (frame_width, frame_height) 형태. 기본 640x480.

#     반환:
#         (u_new, v_new, z_new)
#             u_new, v_new : Optical Flow 기반으로 이동 보정된 뷰파인더 좌표
#             z_new         : Essential Matrix 기반 상대 깊이 값
#     -------------------------------------------------------------
#     처리 흐름:
#       1️⃣ 전 프레임 대비 Optical Flow 인라이어(전역 이동) 이용 → 2D 이동행렬 추정
#       2️⃣ 어파인 변환을 역적용하여 카메라 이동에 따라 마커 보정
#       3️⃣ Essential Matrix 기반의 상대 깊이(z) 추정
#       4️⃣ 결과를 뷰파인더 해상도(0~968,0~857)로 매핑
#     -------------------------------------------------------------
#     주의:
#       - y 축은 OpenCV 이미지 좌표계와 동일하게 아래로 증가.
#       - 따라서 별도의 반전 처리는 필요하지 않음.
#     """

#     # ==========================================================
#     # 🔧 (1) Optical Flow 인라이어 불러오기
#     # ==========================================================
#     from app.ar.motion_core import last_inlier_prev, last_inlier_next, last_parallax_med, K

#     if last_inlier_prev is None or last_inlier_next is None or len(last_inlier_prev) < 8:
#         # Optical Flow 결과가 충분하지 않으면 이동 보정 생략
#         return marker_u, marker_v, 0.0

#     # ==========================================================
#     # 🔧 (2) Affine Transform (전역 2D 이동 추정)
#     # ----------------------------------------------------------
#     #   카메라가 오른쪽으로 움직였다면, 화면의 마커는 왼쪽으로 이동해야 함.
#     #   따라서 전역 이동행렬 H를 계산하고, 역변환 H_inv를 적용한다.
#     # ==========================================================
#     H, inliers = cv2.estimateAffine2D(last_inlier_prev, last_inlier_next, ransacReprojThreshold=2.0)
#     if H is None:
#         return marker_u, marker_v, 0.0

#     # Affine → Homography (3x3)로 확장 후 역행렬 계산
#     try:
#         H_inv = np.linalg.inv(np.vstack([H, [0, 0, 1]]))[:2, :]
#     except np.linalg.LinAlgError:
#         H_inv = np.eye(2, 3, dtype=np.float32)

#     # ==========================================================
#     # 🔧 (3) 뷰파인더 좌표 → 프레임 좌표로 스케일 변환
#     # ==========================================================
#     frame_w, frame_h = frame_shape
#     view_w, view_h = 968, 857

#     u_frame = marker_u * (frame_w / view_w)
#     v_frame = marker_v * (frame_h / view_h)

#     # ==========================================================
#     # 🔧 (4) 역 Affine 변환 적용 (카메라 이동 반영)
#     # ==========================================================
#     p = np.array([[u_frame, v_frame, 1]], dtype=np.float32).T
#     p_new = H_inv @ p
#     u_frame_new, v_frame_new = float(p_new[0, 0]), float(p_new[1, 0])

#     # ==========================================================
#     # 🔧 (5) Essential Matrix 기반 깊이 추정
#     # ----------------------------------------------------------
#     #   motion_core 내부의 last_parallax_med (중앙 시차값)을 이용해
#     #   z를 "상대 깊이" 로 표현.
#     #   - 시차(parallax)가 작을수록 멀리 있음 → z 작게
#     #   - 시차가 크면 가까이 있음 → z 크게
#     # ==========================================================
#     rel_z = 1.0 / (last_parallax_med + 1e-6)
#     z_new = float(rel_z)

#     # ==========================================================
#     # 🔧 (6) 프레임 좌표 → 뷰파인더 좌표로 재변환
#     # ==========================================================
#     u_new = u_frame_new * (view_w / frame_w)
#     v_new = v_frame_new * (view_h / frame_h)

#     # # 화면 경계 보정
#     # u_new = max(0, min(view_w, u_new))
#     # v_new = max(0, min(view_h, v_new))

#     # ==========================================================
#     # 🔧 (7) 반환
#     # ==========================================================
#     return float(u_new), float(v_new), float(z_new)

import os
import cv2
import numpy as np

# ============================
# 🔧 파라미터 (기존 값 유지)
# ============================
MIN_FEATURES = 50
MIN_DIST_BETWEEN = 10.0
MAX_AGE = 30

NCC_THRESH = 0.80          # 템플릿 매칭 임계값
NCC_MIN_REFINED = 8        # refine 후 최소 포인트 수
NCC_MIN_RATIO = 0.3        # refine된 포인트가 OF 포인트의 30% 미만이면 fallback

# intrinsics 로드
def _load_K():
    # app/ar/motion_core.py 기준 ../data/K.npy 를 쓰고 싶으면 아래 주석 해제
    # here = os.path.dirname(__file__)
    # k_path = os.path.join(here, "..", "data", "K.npy")
    # if os.path.exists(k_path):
    #     return np.load(k_path).astype(np.float32)

    # fallback (640x480 가정, 래즈파이 캘리브레이션 값)
    fx, fy, cx, cy = 942.34, 940.92, 315.93, 223.13
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

_latest_gray = None       # 최신 gray 프레임 캐시

# ============================
# 📦 외부 의존
# ============================
from app.ar.feature_extractor import extract_features
from app.ar.feature_tracker import track_features
from app.ar.ransac_filter import ransac_filter
from app.ar.motion_estimator import estimate_motion


# ============================
# 🧭 포즈 관리
# ============================
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


# ============================
# 🧩 Feature Pool 유지
# ============================
def _maintain_feature_pool(gray, prev_valid, next_valid):
    """
    특징점 풀 유지/보강
    - prev_valid, next_valid : (N,1,2)
    """
    global feature_pool

    # === 1) 현재 프레임에서 성공적으로 추적된 점들로 갱신 ===
    if next_valid is not None and len(next_valid) > 0:
        feature_pool["pts"] = next_valid.copy()
        feature_pool["age"] = np.zeros(len(next_valid), dtype=np.int32)
    else:
        # 새 점이 없으면 age 증가
        if feature_pool["age"].size > 0:
            feature_pool["age"] += 1

    # === 2) 너무 오래된 점 제거 ===
    if feature_pool["age"].size > 0:
        valid_mask = feature_pool["age"] < MAX_AGE
        feature_pool["pts"] = feature_pool["pts"][valid_mask]
        feature_pool["age"] = feature_pool["age"][valid_mask]

    # === 3) 부족하면 새 점 채우기 ===
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


# ============================
# 🎬 프레임 처리 (VO 핵심)
# ============================
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
    global _latest_gray

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    _latest_gray = gray.copy()  # 최신 프레임 갱신

    # ===============================
    # 1) 초기 프레임: 특징점만 초기화
    # ===============================
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

    # ===============================
    # 2) Optical Flow (prev_pts → now)
    # ===============================
    prev_pts = feature_pool["pts"]
    if prev_pts is None or len(prev_pts) < 8:
        # 특징점이 너무 부족하면 다시 초기화 시도
        new_pts, _ = extract_features(gray)
        if new_pts is not None and len(new_pts) > 0:
            feature_pool["pts"] = new_pts
            feature_pool["age"] = np.zeros(len(new_pts), dtype=np.int32)
        prev_gray = gray.copy()
        frame_idx += 1
        return {
            "status": "skip",
            "x": float(t_total[0]), "y": float(t_total[1]), "z": float(t_total[2]),
            "inliers": 0, "scale": 1.0,
            "parallax_mean": 0.0, "parallax_med": last_parallax_med,
            "relative_depth_global": 1.0 / (last_parallax_med + 1e-6),
            "R_total": R_total.copy(), "t_total": t_total.copy()
        }

    # Optical Flow 추적
    prev_valid_of, next_valid_of, _ = track_features(
        prev_gray, gray, prev_pts,
        fb_thresh=1.5,
        large_motion_px=100.0,
        enable_equalize=False,
        blur_var_thresh=12.0,
        lk_win_size=(25, 25),
        lk_max_level=4,
        frame=None
    )

    if prev_valid_of is None or len(prev_valid_of) < 8 or \
       next_valid_of is None or len(next_valid_of) < 8:
        # 추적 실패 → 특징점만 새로 뽑고 포즈 업데이트는 생략
        new_pts, _ = extract_features(gray)
        if new_pts is not None and len(new_pts) > 0:
            feature_pool["pts"] = new_pts
            feature_pool["age"] = np.zeros(len(new_pts), dtype=np.int32)
        prev_gray = gray.copy()
        frame_idx += 1
        return {
            "status": "skip",
            "x": float(t_total[0]), "y": float(t_total[1]), "z": float(t_total[2]),
            "inliers": 0, "scale": 1.0,
            "parallax_mean": 0.0, "parallax_med": last_parallax_med,
            "relative_depth_global": 1.0 / (last_parallax_med + 1e-6),
            "R_total": R_total.copy(), "t_total": t_total.copy()
        }

    # ===============================
    # 3) Patch 기반 NCC refine (+ fallback)
    # ===============================
    prev_valid_refined = []
    next_valid_refined = []
    match_scores = []

    patch_hw = 8   # 17x17 템플릿
    search_r = 12  # 25x25 검색 영역

    for (x0, y0), (x1, y1) in zip(prev_valid_of.reshape(-1, 2),
                                  next_valid_of.reshape(-1, 2)):

        # 템플릿 (prev_gray)
        tpl = prev_gray[int(y0 - patch_hw):int(y0 + patch_hw + 1),
                        int(x0 - patch_hw):int(x0 + patch_hw + 1)]
        if tpl.shape[0] != 2 * patch_hw + 1 or tpl.shape[1] != 2 * patch_hw + 1:
            continue

        # 검색 ROI (현재 gray)
        xs0, ys0 = int(x1 - search_r), int(y1 - search_r)
        xs1, ys1 = int(x1 + search_r + 1), int(y1 + search_r + 1)
        roi = gray[max(0, ys0):min(gray.shape[0], ys1),
                   max(0, xs0):min(gray.shape[1], xs1)]
        if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
            continue

        res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        match_scores.append(max_val)

        if max_val >= NCC_THRESH:
            dx, dy = max_loc
            nx = (max(0, xs0) + dx) + patch_hw
            ny = (max(0, ys0) + dy) + patch_hw
            prev_valid_refined.append([x0, y0])
            next_valid_refined.append([nx, ny])

    prev_valid_refined = np.array(prev_valid_refined, dtype=np.float32).reshape(-1, 1, 2) \
        if len(prev_valid_refined) > 0 else np.empty((0, 1, 2), dtype=np.float32)
    next_valid_refined = np.array(next_valid_refined, dtype=np.float32).reshape(-1, 1, 2) \
        if len(next_valid_refined) > 0 else np.empty((0, 1, 2), dtype=np.float32)

    # 평균 NCC 계산 (디버그용)
    mean_score = float(np.mean(match_scores)) if len(match_scores) > 0 else 0.0

    use_refined = False
    if len(prev_valid_refined) >= NCC_MIN_REFINED:
        ratio = len(prev_valid_refined) / float(len(prev_valid_of))
        if ratio >= NCC_MIN_RATIO:
            # refine 결과가 충분히 많고, 비율도 괜찮으면 refine 사용
            use_refined = True
            # print(f"✅ Patch refine: {len(prev_valid_refined)} pts "
            #       f"({ratio*100:.1f}% of OF) | meanNCC={mean_score:.3f}")
    #     else:
    #         print(f"⚠️ Refined ratio too small "
    #               f"({len(prev_valid_refined)}/{len(prev_valid_of)}), "
    #               f"fallback to OF result")
    # else:
    #     print(f"⚠️ Too few refined ({len(prev_valid_refined)}), fallback to OF result")

    if use_refined:
        prev_valid = prev_valid_refined
        next_valid = next_valid_refined
    else:
        prev_valid = prev_valid_of
        next_valid = next_valid_of

    # ===============================
    # 4) Feature pool 유지/보강
    # ===============================
    _maintain_feature_pool(gray, prev_valid, next_valid)

    # ===============================
    # 5) RANSAC + Essential + 포즈 누적
    # ===============================
    status = "skip"
    inliers = 0
    scale = 1.0
    parallax_mean = 0.0
    parallax_med = last_parallax_med  # fallback

    if prev_valid is not None and next_valid is not None and \
       len(prev_valid) >= 8 and len(next_valid) >= 8:

        inlier_prev, inlier_next, F, inlier_mask = ransac_filter(
            prev_valid, next_valid, threshold=1.0, prob=0.999, visualize=False
        )

        if inlier_mask is not None:
            inliers = int(np.count_nonzero(inlier_mask))

            if inliers >= 8:
                # --- 시차 통계 계산 ---
                parallax = np.linalg.norm(inlier_next - inlier_prev, axis=1)  # (N,)
                if parallax.size > 0:
                    parallax_mean = float(np.mean(parallax))
                    parallax_med = float(np.median(parallax))
                    if parallax_med <= 1e-9:
                        parallax_med = 1e-6
                else:
                    parallax_mean = 0.0
                    parallax_med = last_parallax_med

                # 캐시 갱신 (size / 마커 보정용)
                last_inlier_prev = inlier_prev.reshape(-1, 2).copy()
                last_inlier_next = inlier_next.reshape(-1, 2).copy()
                last_parallax = parallax.copy()
                last_parallax_med = parallax_med

                # --- Essential 기반 모션 ---
                R, t, E, stats = estimate_motion(inlier_prev, inlier_next, K)
                if stats.get("pose_ok", False):
                    scale = float(stats.get("scale", 1.0))

                    # 너무 작은 이동은 노이즈로 간주하고 무시할 수도 있음 (옵션)
                    if np.linalg.norm(t) > 1e-6:
                        # 누적 포즈 갱신: t_total = t_total + R_total @ (scale * t)
                        #                  R_total = R @ R_total
                        t_total += R_total @ (scale * t)
                        R_total = R @ R_total
                        status = "ok"
                else:
                    print("⚠️ estimate_motion returned pose_ok=False")

    prev_gray = gray.copy()
    frame_idx += 1

    relative_depth_global = 1.0 / (parallax_med + 1e-6)  # 전역 깊이 스케일

    return {
        "status": status,
        "x": float(t_total[0]), "y": float(t_total[1]), "z": float(t_total[2]),
        "inliers": inliers, "scale": scale,
        "parallax_mean": parallax_mean, "parallax_med": parallax_med,
        "relative_depth_global": float(relative_depth_global),
        "R_total": R_total.copy(), "t_total": t_total.copy()
    }


# ============================
# 📐 픽셀 → 월드(z=const 평면) 변환
# ============================
def pixel_to_world_on_plane(u, v, plane_z=0.0):
    """
    현재 포즈(R_total, t_total)와 K를 사용해 이미지 픽셀(u,v)의 광선을
    월드 z=plane_z 평면과 교차시켜 3D 좌표를 구함.
    반환: (x, y, z) or None

    - 포즈가 초기화되지 않았으면 None
    - 광선이 평면과 거의 평행이면 plane_z를 보정
    """
    global R_total, t_total, K

    # ① 포즈 유효성 검사
    if np.allclose(t_total, 0, atol=1e-6):
        print("⚠️ [pixel_to_world_on_plane] Pose not initialized (t_total≈0). Returning None.")
        return None

    # ② 내참수 추출
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    # ③ 픽셀 → 카메라 좌표계 방향벡터
    x_cam = (u - cx) / fx
    y_cam = (v - cy) / fy
    dir_cam = np.array([x_cam, y_cam, 1.0], dtype=np.float32).reshape(3, 1)

    # ④ 카메라 → 월드 방향 변환
    dir_world = (R_total @ dir_cam).reshape(3)
    C = t_total.reshape(3)
    denom = dir_world[2]

    # ⑤ 평면과 평행한 경우 보정
    if abs(denom) < 1e-8:
        print("⚠️ [pixel_to_world_on_plane] Ray nearly parallel to plane_z, adjusting plane_z→-1.0")
        plane_z = -1.0
        denom = dir_world[2] if abs(dir_world[2]) > 1e-8 else 1e-8

    # ⑥ 평면 교차점 계산
    t = (plane_z - C[2]) / denom
    if t <= 0:
        print(f"⚠️ [pixel_to_world_on_plane] Intersection behind camera (t={t:.4f}) → returning None.")
        return None

    P = C + t * dir_world
    wx, wy, wz = float(P[0]), float(P[1]), float(P[2])
    return wx, wy, wz


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
    정의: local_parallax / global_median_parallax
    - parallax(시차)가 클수록 가깝다 → 값이 클수록 '가깝다/커 보인다'
    """
    global last_parallax_med
    local = _knn_local_parallax(u, v, k=k)
    if local is None or local <= 1e-9:
        return None
    return float((local + 1e-6) / (last_parallax_med + 1e-6))


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
    mask = (pts[:, 0] >= x_min) & (pts[:, 0] <= x_max) & \
           (pts[:, 1] >= y_min) & (pts[:, 1] <= y_max)
    if not np.any(mask):
        return None

    local_med = float(np.median(last_parallax[mask]))
    if local_med <= 1e-9:
        return None
    return float((local_med + 1e-6) / (last_parallax_med + 1e-6))


# ============================
# 🧩 최신 gray & 패치 유틸
# ============================
def get_latest_gray():
    """가장 최근 프레임의 gray 이미지를 반환"""
    global _latest_gray
    return _latest_gray


def extract_patch_from_current_gray(u, v, half_size=10):
    """현재 gray 프레임에서 (u,v) 근처 패치를 잘라 반환"""
    global _latest_gray
    if _latest_gray is None:
        return None
    h, w = _latest_gray.shape
    u, v = int(u), int(v)
    x0, y0 = max(0, u - half_size), max(0, v - half_size)
    x1, y1 = min(w, u + half_size + 1), min(h, v + half_size + 1)
    patch = _latest_gray[y0:y1, x0:x1]
    if patch.shape[0] < 2 * half_size or patch.shape[1] < 2 * half_size:
        return None
    return patch.copy()


def refine_patch_position(gray_now, u_pred, v_pred, tpl, search_r=14):
    """
    현재 프레임(gray_now)에서 예측좌표(u_pred,v_pred) 근방을 탐색하여
    템플릿(tpl)과 가장 유사한 위치를 반환.
    """
    h, w = gray_now.shape[:2]
    half_t = tpl.shape[0] // 2
    x0, y0 = int(u_pred - search_r), int(v_pred - search_r)
    x1, y1 = int(u_pred + search_r + 1), int(v_pred + search_r + 1)

    x0c, y0c = max(0, x0), max(0, y0)
    x1c, y1c = min(w, x1), min(h, y1)
    roi = gray_now[y0c:y1c, x0c:x1c]

    if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
        return (u_pred, v_pred, 0.0)

    res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < 0.7:
        return (u_pred, v_pred, max_val)

    dx, dy = max_loc
    u_ref = (x0c + dx) + half_t
    v_ref = (y0c + dy) + half_t
    return (float(u_ref), float(v_ref), float(max_val))


# ============================
# 📍 마커 좌표 업데이트
# ============================
def update_marker_position(marker_u, marker_v, frame_shape=(640, 480)):
    """
    📍 Optical Flow + Essential Matrix 기반 마커 좌표 업데이트

    이 함수는 클라이언트 뷰파인더(0~968, 0~857) 상의 클릭 좌표 (u,v)를
    최신 프레임의 카메라 움직임에 맞춰 보정해주는 역할을 한다.

    입력:
        marker_u, marker_v : float
            클라이언트에서 들어온 마커의 초기 클릭 좌표 (뷰파인더 기준)
        frame_shape : tuple(int, int)
            (frame_width, frame_height) 형태. 기본 640x480.

    반환:
        (u_new, v_new, z_new)
            u_new, v_new : Optical Flow 기반으로 이동 보정된 뷰파인더 좌표
            z_new         : Essential Matrix 기반 상대 깊이 값 (글로벌 시차 기반)
    """
    global last_inlier_prev, last_inlier_next, last_parallax_med

    # 1) 인라이어가 충분하지 않으면 그대로 반환
    if last_inlier_prev is None or last_inlier_next is None or \
       len(last_inlier_prev) < 8 or len(last_inlier_next) < 8:
        return marker_u, marker_v, 0.0

    # 2) Affine Transform (전역 2D 이동 추정)
    H, inliers = cv2.estimateAffine2D(
        last_inlier_prev.reshape(-1, 1, 2),
        last_inlier_next.reshape(-1, 1, 2),
        ransacReprojThreshold=2.0
    )
    if H is None:
        return marker_u, marker_v, 0.0

    # Affine → Homography(3x3) 확장 후 역행렬
    try:
        H_h = np.vstack([H, [0, 0, 1]])
        H_inv = np.linalg.inv(H_h)[:2, :]
    except np.linalg.LinAlgError:
        H_inv = np.eye(2, 3, dtype=np.float32)

    # 3) 뷰파인더 좌표 → 프레임 좌표 스케일 변환
    frame_w, frame_h = frame_shape
    view_w, view_h = 968, 857

    u_frame = marker_u * (frame_w / view_w)
    v_frame = marker_v * (frame_h / view_h)

    # 4) 역 Affine 변환 적용 (카메라 이동 반영)
    p = np.array([[u_frame, v_frame, 1]], dtype=np.float32).T
    p_new = H_inv @ p
    u_frame_new, v_frame_new = float(p_new[0, 0]), float(p_new[1, 0])

    # 5) 깊이 추정 (전역 시차 기반 상대 깊이)
    rel_z = 1.0 / (last_parallax_med + 1e-6)
    z_new = float(rel_z)

    # 6) 프레임 좌표 → 뷰파인더 좌표 재변환
    u_new = u_frame_new * (view_w / frame_w)
    v_new = v_frame_new * (view_h / frame_h)

    return float(u_new), float(v_new), float(z_new)
