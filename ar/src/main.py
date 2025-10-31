# # 📄 main.py
# import cv2
# import numpy as np
# import os
# import time

# from video_loader import load_video
# from feature_extractor import extract_features
# from ransac_filter import ransac_filter
# from motion_estimator import estimate_motion  # ✅ Essential Matrix + Pose

# # ===== 파라미터 =====
# MIN_TRACKS = 60
# REFRESH_EVERY = 25
# DISPLAY_SCALE = 0.8
# CALIB_PATH = "../data/camera_intrinsics.npy"
# DIST_PATH = "../data/dist_coeffs.npy"
# TRAJ_SIZE = 600
# SCALE_FACTOR = 5.0  # 프레임 간 이동 스케일 (임의 조정 가능)


# def draw_points(frame, points, color=(0, 255, 0)):
#     """특징점 시각화"""
#     if points is None or len(points) == 0:
#         return frame
#     for p in points:
#         x, y = p.ravel()
#         cv2.circle(frame, (int(x), int(y)), 2, color, -1)
#     return frame


# def draw_flow(frame, good_old, good_new, color=(0, 255, 0)):
#     """Optical Flow 시각화"""
#     mask = np.zeros_like(frame)
#     for (new, old) in zip(good_new, good_old):
#         a, b = new.ravel()
#         c, d = old.ravel()
#         cv2.line(mask, (int(a), int(b)), (int(c), int(d)), color, 1)
#         cv2.circle(frame, (int(a), int(b)), 2, (0, 0, 255), -1)
#     return cv2.add(frame, mask)


# def main():
#     print("🎬 Optical Flow → RANSAC → Essential → Pose(R,t) 누적 궤적 시작")

#     # 🎥 영상
#     video = load_video("../data/3.mp4")

#     # 🎯 카메라 캘리브레이션
#     K = np.load(CALIB_PATH) if os.path.exists(CALIB_PATH) else None
#     D = np.load(DIST_PATH) if os.path.exists(DIST_PATH) else None
#     use_pose = K is not None
#     if use_pose:
#         print("✅ K 로드됨 → Essential Matrix 기반 Pose 추정 사용")
#     else:
#         print("ℹ️ K 없음 → Fundamental RANSAC만 수행 (이동 시각화 X)")

#     # === 출력 디렉토리 ===
#     base_output = "../output"
#     dirs = {n: os.path.join(base_output, n) for n in ["features", "optical_flow", "ransac", "trajectory"]}
#     [os.makedirs(d, exist_ok=True) for d in dirs.values()]

#     # === 첫 프레임 ===
#     ret, prev_frame = video.read()
#     if not ret:
#         print("❌ 첫 프레임 읽기 실패")
#         return

#     prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
#     prev_pts = extract_features(prev_gray)
#     frame_idx = 0

#     # --- Trajectory 시각화용 상태 ---
#     traj = np.zeros((TRAJ_SIZE, TRAJ_SIZE, 3), dtype=np.uint8)
#     R_total = np.eye(3)
#     t_total = np.zeros((3, 1))
#     center = TRAJ_SIZE // 2

#     while True:
#         ret, frame = video.read()
#         if not ret:
#             print("✅ 모든 프레임 처리 완료")
#             break

#         start_time = time.time()
#         gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#         h, w = gray.shape[:2]

#         # (1) 주기적 특징점 재검출
#         if REFRESH_EVERY and frame_idx % REFRESH_EVERY == 0 and frame_idx > 0:
#             prev_pts = extract_features(prev_gray)

#         flow_vis, ransac_vis = frame.copy(), frame.copy()
#         inlier_next = None

#         # (2) Optical Flow
#         if prev_pts is not None and len(prev_pts) > 0:
#             next_pts, status, err = cv2.calcOpticalFlowPyrLK(
#                 prev_gray, gray, prev_pts, None,
#                 winSize=(21, 21), maxLevel=3,
#                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
#             )

#             if next_pts is not None and status is not None:
#                 good_new = next_pts[status.flatten() == 1]
#                 good_old = prev_pts[status.flatten() == 1]
#                 flow_vis = draw_flow(flow_vis, good_old, good_new)

#                 if len(good_new) < MIN_TRACKS:
#                     print("⚠️ 특징점 부족, 재검출")
#                     prev_pts = extract_features(gray)
#                 else:
#                     # (3) RANSAC 필터링
#                     inlier_prev, inlier_next, mask_r, F = ransac_filter(good_old, good_new)

#                     if inlier_prev is not None and len(inlier_prev) >= 8:
#                         # (4) Essential Matrix + Pose 계산
#                         if use_pose:
#                             R, t, E = estimate_motion(inlier_prev, inlier_next, K)
#                             if R is not None and t is not None:
#                                 # --- Pose 누적 (세계좌표 기준 이동 경로 추정) ---
#                                 scale = SCALE_FACTOR
#                                 R_total = R @ R_total
#                                 t_total += R_total @ (t * scale)

#                                 # 시각화용 정보
#                                 pos = t_total.copy()
#                                 x = int(center + pos[0, 0])
#                                 z = int(center + pos[2, 0])
#                                 cv2.circle(traj, (x, z), 2, (0, 255, 0), -1)
#                                 cv2.putText(ransac_vis, f"t = {np.round(t.flatten(), 3)}",
#                                             (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
#                         else:
#                             print("ℹ️ Fundamental RANSAC만 수행 (Pose 계산 생략)")

#                         # (5) 인라이어 시각화
#                         for (new, old, ok) in zip(good_new, good_old, mask_r):
#                             a, b = new.ravel()
#                             c, d = old.ravel()
#                             color = (0, 255, 0) if ok else (0, 0, 255)
#                             cv2.line(ransac_vis, (int(a), int(b)), (int(c), int(d)), color, 1)
#                             cv2.circle(ransac_vis, (int(a), int(b)), 2, color, -1)
#                         cv2.putText(ransac_vis, f"Inliers: {np.sum(mask_r)}/{len(mask_r)}",
#                                     (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
#                     else:
#                         print("❌ RANSAC 실패 → 특징점 재검출")
#                         prev_pts = extract_features(gray)
#             else:
#                 print("⚠️ Optical Flow 실패 — 특징점 재검출")
#                 prev_pts = extract_features(gray)
#         else:
#             print("⚠️ 추적점 없음 — 특징점 재검출")
#             prev_pts = extract_features(gray)

#         # (6) 결과 저장
#         feat_img = draw_points(frame.copy(), prev_pts)
#         cv2.imwrite(os.path.join(dirs["features"], f"feature_{frame_idx:05d}.jpg"), feat_img)
#         cv2.imwrite(os.path.join(dirs["optical_flow"], f"flow_{frame_idx:05d}.jpg"), flow_vis)
#         cv2.imwrite(os.path.join(dirs["ransac"], f"ransac_{frame_idx:05d}.jpg"), ransac_vis)

#         # (7) Trajectory 시각화
#         traj_vis = traj.copy()
#         cv2.putText(traj_vis,
#                     f"Pos: [{t_total[0,0]:.1f}, {t_total[1,0]:.1f}, {t_total[2,0]:.1f}]",
#                     (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
#         cv2.imwrite(os.path.join(dirs["trajectory"], f"traj_{frame_idx:05d}.jpg"), traj_vis)

#         # (8) 화면 표시
#         disp1 = cv2.resize(feat_img, (int(w * DISPLAY_SCALE), int(h * DISPLAY_SCALE)))
#         disp2 = cv2.resize(flow_vis, (int(w * DISPLAY_SCALE), int(h * DISPLAY_SCALE)))
#         disp3 = cv2.resize(ransac_vis, (int(w * DISPLAY_SCALE), int(h * DISPLAY_SCALE)))
#         disp4 = cv2.resize(traj_vis, (int(TRAJ_SIZE * 0.6), int(TRAJ_SIZE * 0.6)))

#         cv2.imshow("Feature Points", disp1)
#         cv2.imshow("Optical Flow", disp2)
#         cv2.imshow("RANSAC / Pose", disp3)
#         cv2.imshow("Trajectory (x-z)", disp4)

#         if cv2.waitKey(20) & 0xFF in (ord('q'), 27):
#             break

#         # (9) 다음 루프 준비
#         prev_gray = gray.copy()
#         prev_pts = inlier_next.reshape(-1, 1, 2) if inlier_next is not None and len(inlier_next) > 0 else extract_features(gray)

#         frame_idx += 1
#         elapsed = (time.time() - start_time) * 1000
#         print(f"🕒 Frame {frame_idx:03d} 처리 완료 ({elapsed:.1f} ms)")

#     # 종료
#     video.release()
#     cv2.destroyAllWindows()
#     print(f"\n💾 총 {frame_idx}개 프레임 저장 완료:")
#     for k, v in dirs.items():
#         print(f"  - {k}: {v}")


# if __name__ == "__main__":
#     main()


import cv2
import numpy as np
import os
import time

from video_loader import load_video
from feature_extractor import extract_features
from ransac_filter import ransac_filter
from motion_estimator import estimate_motion  # ✅ Essential Matrix + Pose

# ===== 파라미터 =====
MIN_TRACKS = 60
REFRESH_EVERY = 25
DISPLAY_SCALE = 0.8
CALIB_PATH = "../data/camera_intrinsics.npy"
DIST_PATH = "../data/dist_coeffs.npy"
TRAJ_SIZE = 600
SCALE_FACTOR = 5.0
MAX_FRAMES = 300  # 프로파일링용 제한


def timed(func, label, log_dict):
    """단계별 수행시간(ms) 기록용 데코레이터"""
    start = time.perf_counter()
    result = func()
    elapsed = (time.perf_counter() - start) * 1000
    log_dict[label].append(elapsed)
    return result, elapsed


def main():
    print("🎬 Optical Flow → RANSAC → Essential → Pose(R,t) 프로파일링 시작")

    # 🎥 영상 로드
    video = load_video("../data/3.mp4")

    # 🎯 카메라 파라미터
    K = np.load(CALIB_PATH) if os.path.exists(CALIB_PATH) else None
    D = np.load(DIST_PATH) if os.path.exists(DIST_PATH) else None
    use_pose = K is not None
    print("✅ K 로드됨 → Essential Matrix 기반 Pose 추정 사용" if use_pose
          else "ℹ️ K 없음 → Fundamental RANSAC만 수행 (이동 시각화 X)")

    # 출력 디렉토리
    base_output = "../output"
    dirs = {n: os.path.join(base_output, n) for n in ["features", "optical_flow", "ransac", "trajectory"]}
    [os.makedirs(d, exist_ok=True) for d in dirs.values()]

    # 프로파일링 데이터
    time_log = {
        "optical_flow": [],
        "ransac": [],
        "pose": [],
        "total": []
    }

    # 초기화
    ret, prev_frame = video.read()
    if not ret:
        print("❌ 첫 프레임 읽기 실패")
        return

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_pts = extract_features(prev_gray)
    frame_idx = 0

    traj = np.zeros((TRAJ_SIZE, TRAJ_SIZE, 3), dtype=np.uint8)
    R_total = np.eye(3)
    t_total = np.zeros((3, 1))
    center = TRAJ_SIZE // 2

    while True:
        ret, frame = video.read()
        if not ret or frame_idx >= MAX_FRAMES:
            break

        total_start = time.perf_counter()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if REFRESH_EVERY and frame_idx % REFRESH_EVERY == 0 and frame_idx > 0:
            prev_pts = extract_features(prev_gray)

        flow_vis, ransac_vis = frame.copy(), frame.copy()
        inlier_next = None

        # Optical Flow
        if prev_pts is not None and len(prev_pts) > 0:
            def run_optical_flow():
                return cv2.calcOpticalFlowPyrLK(
                    prev_gray, gray, prev_pts, None,
                    winSize=(21, 21), maxLevel=3,
                    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
                )

            (next_pts, status, err), t_flow = timed(run_optical_flow, "optical_flow", time_log)

            if next_pts is not None and status is not None:
                good_new = next_pts[status.flatten() == 1]
                good_old = prev_pts[status.flatten() == 1]

                if len(good_new) >= MIN_TRACKS:
                    # RANSAC
                    def run_ransac():
                        return ransac_filter(good_old, good_new)
                    (inlier_prev, inlier_next, mask_r, F), t_ransac = timed(run_ransac, "ransac", time_log)

                    # Pose (Essential)
                    if use_pose and inlier_prev is not None and len(inlier_prev) >= 8:
                        def run_pose():
                            return estimate_motion(inlier_prev, inlier_next, K)
                        (R, t, E), t_pose = timed(run_pose, "pose", time_log)

                        if R is not None and t is not None:
                            R_total = R @ R_total
                            t_total += R_total @ (t * SCALE_FACTOR)

                            pos = t_total.copy()
                            x = int(center + pos[0, 0])
                            z = int(center + pos[2, 0])
                            cv2.circle(traj, (x, z), 2, (0, 255, 0), -1)
                            cv2.putText(ransac_vis, f"t = {np.round(t.flatten(), 3)}",
                                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
                else:
                    prev_pts = extract_features(gray)
        else:
            prev_pts = extract_features(gray)

        elapsed_total = (time.perf_counter() - total_start) * 1000
        time_log["total"].append(elapsed_total)

        prev_gray = gray.copy()
        prev_pts = inlier_next.reshape(-1, 1, 2) if inlier_next is not None and len(inlier_next) > 0 else extract_features(gray)

        frame_idx += 1
        print(f"🕒 Frame {frame_idx:03d} 처리 완료 ({elapsed_total:.1f} ms)")

    # 종료
    video.release()
    cv2.destroyAllWindows()

    print("\n📊 === 단계별 평균 처리시간 (ms/frame) ===")
    for key, vals in time_log.items():
        if len(vals) > 0:
            avg = np.mean(vals)
            print(f"{key:>12}: {avg:6.2f} ms ({1000/avg:.1f} FPS)")
    print("==========================================")


if __name__ == "__main__":
    main()
