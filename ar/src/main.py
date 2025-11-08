import cv2
import numpy as np
import os
from feature_extractor import extract_features
from feature_tracker import track_features
from ransac_filter import ransac_filter  

# ==========================================================
# 🎯 설정
# ==========================================================
VIDEO_PATH = "../data/3.mp4"            # 입력 비디오 경로
OUTPUT_FLOW_DIR = "../output/optical_flow" # Optical Flow 결과 저장 경로
OUTPUT_RANSAC_DIR = "../output/ransac"     # RANSAC 결과 저장 경로
DISPLAY_SCALE = 1.0                        # 보기용 축소 비율

# 색상
FLOW_COLOR = (0, 255, 255)                 # Optical Flow 선 (노란색)
POINT_COLOR = (0, 255, 0)                  # 기존 추적 점 (초록)
NEW_POINT_COLOR = (255, 0, 0)              # 새로 추가된 점 (파랑)
REMOVED_POINT_COLOR = (0, 0, 255)          # 제거/소실 (빨강)
RANSAC_INLIER_COLOR = (0, 255, 0)          # RANSAC 인라이어 (초록)
RANSAC_OUTLIER_COLOR = (0, 0, 255)         # RANSAC 아웃라이어 (빨강)

# 유지/보충 파라미터
MIN_FEATURES = 50                          # 최소 유지할 특징점 수
MIN_DIST_BETWEEN = 10.0                    # 기존 점들과의 최소 거리(px)
MAX_AGE = 30                               # 추적 실패시 유지 프레임 수

# ==========================================================
# 🎥 시각화 함수
# ==========================================================
def draw_feature_groups(vis_frame, tracked_pts, new_pts=None, removed_pts=None):
    """
    각 점 그룹별로 시각화:
      - 초록: 현재 유지 중(feature_pool["pts"])
      - 파랑: 이번 프레임에 새로 추가
      - 빨강: 이번 프레임에서 사라진 점(이전엔 있었는데 next_valid에 없음)
    """
    vis = vis_frame.copy()
    if tracked_pts is not None and len(tracked_pts) > 0:
        for p in tracked_pts.reshape(-1, 2):
            cv2.circle(vis, (int(p[0]), int(p[1])), 2, POINT_COLOR, -1)
    if new_pts is not None and len(new_pts) > 0:
        for p in new_pts.reshape(-1, 2):
            cv2.circle(vis, (int(p[0]), int(p[1])), 2, NEW_POINT_COLOR, -1)
    if removed_pts is not None and len(removed_pts) > 0:
        for p in removed_pts.reshape(-1, 2):
            cv2.circle(vis, (int(p[0]), int(p[1])), 2, REMOVED_POINT_COLOR, -1)
    return vis


def draw_optical_flow(vis_frame, prev_pts, next_pts, color=(0, 255, 255)):
    """
    Optical Flow로 추적된 점 쌍을 화살표로 시각화
    """
    vis = vis_frame.copy()
    if prev_pts is None or next_pts is None or len(prev_pts) == 0:
        return vis

    n = min(len(prev_pts), len(next_pts))
    p1s = prev_pts.reshape(-1, 2)[:n]
    p2s = next_pts.reshape(-1, 2)[:n]

    for (x1, y1), (x2, y2) in zip(p1s, p2s):
        cv2.arrowedLine(vis, (int(x1), int(y1)), (int(x2), int(y2)), color, 1, tipLength=0.3)
        cv2.circle(vis, (int(x2), int(y2)), 2, (0, 255, 0), -1)
    return vis


def draw_ransac_matches(frame, prev_pts, next_pts, inlier_mask):
    """
    RANSAC 결과(인라이어/아웃라이어)를 한 장의 프레임에 시각화.
      - 인라이어: 초록 선/점
      - 아웃라이어: 빨강 선/점
    입력:
      prev_pts, next_pts: (N,1,2) 또는 (N,2)
      inlier_mask: (N,) bool
    """
    vis = frame.copy()
    if prev_pts is None or next_pts is None or inlier_mask is None:
        return vis

    p1 = np.squeeze(prev_pts).astype(np.float32)
    p2 = np.squeeze(next_pts).astype(np.float32)
    if p1.ndim != 2 or p2.ndim != 2 or len(p1) == 0:
        return vis

    inlier_mask = inlier_mask.astype(bool)
    for (a, b, is_in) in zip(p1, p2, inlier_mask):
        c = RANSAC_INLIER_COLOR if is_in else RANSAC_OUTLIER_COLOR
        x1, y1 = int(np.clip(a[0], 0, vis.shape[1] - 1)), int(np.clip(a[1], 0, vis.shape[0] - 1))
        x2, y2 = int(np.clip(b[0], 0, vis.shape[1] - 1)), int(np.clip(b[1], 0, vis.shape[0] - 1))
        cv2.line(vis, (x1, y1), (x2, y2), c, 1)
        cv2.circle(vis, (x2, y2), 2, c, -1)
    return vis


# ==========================================================
# 🎬 메인 Optical Flow + RANSAC 루프
# ==========================================================
def main():
    os.makedirs(OUTPUT_FLOW_DIR, exist_ok=True)
    os.makedirs(OUTPUT_RANSAC_DIR, exist_ok=True)

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("❌ 비디오를 열 수 없습니다.")
        return

    print("🎬 Persistent Optical Flow + RANSAC (Fundamental) ...")

    prev_gray = None
    frame_idx = 0

    # 점 풀 (좌표 + age)
    feature_pool = {
        "pts": np.empty((0, 1, 2), dtype=np.float32),
        "age": np.empty((0,), dtype=np.int32)
    }

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 첫 프레임 초기화
        if prev_gray is None:
            init_pts, method = extract_features(gray)
            feature_pool["pts"] = init_pts
            feature_pool["age"] = np.zeros(len(init_pts), dtype=np.int32)
            print(f"[{frame_idx:04d}] {method}: {len(init_pts)} initial points")
            prev_gray = gray.copy()
            frame_idx += 1
            continue

        prev_pts = feature_pool["pts"]

        # === Optical Flow 추적 ===
        prev_valid, next_valid, _ = track_features(
            prev_gray, gray, prev_pts,
            fb_thresh=1.5,
            large_motion_px=60.0,
            enable_equalize=False,
            blur_var_thresh=12.0,
            lk_win_size=(25, 25),
            lk_max_level=4
        )

        # Optical Flow 시각화용 복사본
        flow_prev = prev_valid.copy()
        flow_next = next_valid.copy()

        # 🔸 이전 프레임에서 사라진 점(= 제거된 점) 추정 (시각화용)
        removed_pts = np.empty((0, 1, 2), dtype=np.float32)
        if len(prev_pts) > 0 and len(next_valid) > 0:
            prev_set = {tuple(p[0]) for p in prev_pts}
            next_set = {tuple(p[0]) for p in next_valid}
            missing = prev_set - next_set
            if missing:
                removed_pts = np.array([[p] for p in missing], dtype=np.float32)

        # Optical Flow 성공 시 풀 교체, 실패 시 age 증가
        if len(next_valid) > 0:
            feature_pool["pts"] = next_valid
            feature_pool["age"] = np.zeros(len(next_valid), dtype=np.int32)
        else:
            feature_pool["age"] += 1

        # age 관리 — 오래된 점 제거, 보호 점은 유지
        feature_pool["age"][feature_pool["age"] < 0] += 1  # 보호 프레임 감소
        valid_mask = feature_pool["age"] < MAX_AGE
        feature_pool["pts"] = feature_pool["pts"][valid_mask]
        feature_pool["age"] = feature_pool["age"][valid_mask]

        # === 새 점 보충 ===
        added_pts = np.empty((0, 1, 2), dtype=np.float32)
        if len(feature_pool["pts"]) < MIN_FEATURES:
            new_pts, _ = extract_features(gray)
            if new_pts is not None and len(new_pts) > 0:
                if len(feature_pool["pts"]) > 0:
                    dist = np.linalg.norm(
                        new_pts.reshape(-1, 1, 2) - feature_pool["pts"].reshape(1, -1, 2),
                        axis=2
                    )
                    if dist.shape[1] > 0:
                        mask_far = (dist.min(axis=1) > MIN_DIST_BETWEEN)
                        added_pts = new_pts[mask_far]
                else:
                    added_pts = new_pts

                if len(added_pts) > 0:
                    feature_pool["pts"] = np.vstack((feature_pool["pts"], added_pts))
                    ages = np.full(len(added_pts), -MAX_AGE, dtype=np.int32)  # 새 점 보호 시작
                    feature_pool["age"] = np.concatenate((feature_pool["age"], ages))
                    print(f"[{frame_idx:04d}] 🔹 Added {len(added_pts)} new points (total {len(feature_pool['pts'])})")
            else:
                print(f"[{frame_idx:04d}] ⚠️ Unable to add new features")
        else:
            print(f"[{frame_idx:04d}] Maintaining {len(feature_pool['pts'])} points")

        # === (A) Optical Flow 결과 시각화/저장 ===
        vis_points = draw_feature_groups(frame, feature_pool["pts"], new_pts=added_pts, removed_pts=removed_pts)
        vis_flow = draw_optical_flow(frame, flow_prev, flow_next)
        combined_flow = np.hstack((vis_points, vis_flow))

        cv2.putText(combined_flow, f"Tracked: {len(feature_pool['pts'])}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        out_flow = os.path.join(OUTPUT_FLOW_DIR, f"flow_{frame_idx:04d}.jpg")
        cv2.imwrite(out_flow, combined_flow)

        # === (B) RANSAC (Fundamental) 적용 / 결과 시각화/저장 ===
        # 주의: RANSAC은 “정제(denoising)” 목적. 3D 복원은 Essential 단계에서.
        if len(flow_prev) >= 8 and len(flow_next) >= 8:
            inlier_prev, inlier_next, F, inlier_mask = ransac_filter(
                flow_prev, flow_next,
                threshold=1.0,   # 장면에 따라 0.8~1.5
                prob=0.999,
                visualize=False  # 별도 창 표시 안함 (파일 저장으로 대체)
            )
            if inlier_mask is not None and len(inlier_mask) == len(flow_prev):
                vis_ransac = draw_ransac_matches(frame, flow_prev, flow_next, inlier_mask)
                cv2.putText(vis_ransac,
                            f"RANSAC Inliers: {np.count_nonzero(inlier_mask)}/{len(inlier_mask)}",
                            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
                out_ransac = os.path.join(OUTPUT_RANSAC_DIR, f"ransac_{frame_idx:04d}.jpg")
                cv2.imwrite(out_ransac, vis_ransac)

        # === 보기용 윈도우 (Optical Flow 화면) ===
        disp = cv2.resize(combined_flow,
                          (int(combined_flow.shape[1]*DISPLAY_SCALE),
                           int(combined_flow.shape[0]*DISPLAY_SCALE)))
        cv2.imshow("Persistent Optical Flow (Pre-RANSAC)", disp)

        # 다음 프레임 준비
        prev_gray = gray.copy()
        frame_idx += 1

        if cv2.waitKey(10) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"✅ 저장 완료: {OUTPUT_FLOW_DIR} (Optical Flow), {OUTPUT_RANSAC_DIR} (RANSAC)")
    

# ==========================================================
if __name__ == "__main__":
    main()
