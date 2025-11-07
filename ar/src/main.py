import cv2
import numpy as np
import os
from feature_extractor import extract_features
from feature_tracker import track_features

# ==========================================================
# 🎯 설정
# ==========================================================
VIDEO_PATH = "../data/test.mp4"            # 입력 비디오 경로
OUTPUT_DIR = "../output/optical_flow"      # Optical Flow 결과 저장 경로
DISPLAY_SCALE = 1.0                        # 보기용 축소 비율
FLOW_COLOR = (0, 255, 255)                 # Optical Flow 선 색상 (노란색)
POINT_COLOR = (0, 255, 0)                  # 기존 특징점 (초록색)
NEW_POINT_COLOR = (255, 0, 0)              # 새로 추가된 특징점 (파란색)
MIN_FEATURES = 50                          # 최소 유지할 특징점 개수
MIN_DIST_BETWEEN = 10.0                    # 기존 점과의 최소 거리(px)
MAX_AGE = 30                                # 추적 실패 시 유지할 프레임 수

# ==========================================================
# 🎥 시각화 함수
# ==========================================================
def draw_features(vis_frame, tracked_pts, new_pts=None):
    """
    기존 점(초록)과 새 점(파랑)을 표시
    """
    vis = vis_frame.copy()
    if tracked_pts is not None and len(tracked_pts) > 0:
        for p in tracked_pts.reshape(-1, 2):
            cv2.circle(vis, (int(p[0]), int(p[1])), 2, POINT_COLOR, -1)
    if new_pts is not None and len(new_pts) > 0:
        for p in new_pts.reshape(-1, 2):
            cv2.circle(vis, (int(p[0]), int(p[1])), 2, NEW_POINT_COLOR, -1)
    return vis


def draw_optical_flow(vis_frame, prev_pts, next_pts, color=(0, 255, 255)):
    """
    Optical Flow로 추적된 점 쌍을 화살표로 시각화
    """
    vis = vis_frame.copy()
    if prev_pts is None or next_pts is None:
        return vis
    n_prev = len(prev_pts)
    n_next = len(next_pts)
    if n_prev == 0 or n_next == 0:
        return vis

    # 쌍 개수가 다르면 최소 길이에 맞춰 그림
    n = min(n_prev, n_next)
    p1s = prev_pts.reshape(-1, 2)[:n]
    p2s = next_pts.reshape(-1, 2)[:n]

    for (x1, y1), (x2, y2) in zip(p1s, p2s):
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        cv2.arrowedLine(vis, (x1, y1), (x2, y2), color, 1, tipLength=0.3)
        cv2.circle(vis, (x2, y2), 2, (0, 255, 0), -1)
    return vis


# ==========================================================
# 🎬 메인 루프
# ==========================================================
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("❌ 비디오를 열 수 없습니다.")
        return

    print("🎬 Persistent Optical Flow (RANSAC 전단계)...")

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

        # === 첫 프레임 초기화 ===
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
        prev_valid, next_valid, mask = track_features(
            prev_gray, gray, prev_pts,
            fb_thresh=1.5,
            large_motion_px=60.0,
            enable_equalize=False,
            blur_var_thresh=12.0,
            lk_win_size=(25, 25),
            lk_max_level=4
        )

        # Optical Flow 시각화용 쌍 저장
        flow_prev = prev_valid.copy()
        flow_next = next_valid.copy()

        # Optical Flow 성공한 점 갱신
        if len(next_valid) > 0:
            feature_pool["pts"] = next_valid
            feature_pool["age"] = np.zeros(len(next_valid), dtype=np.int32)
        else:
            # Optical Flow 실패 시 age 증가
            feature_pool["age"] += 1

        # 오래된 점 제거
        valid_mask = feature_pool["age"] < MAX_AGE
        feature_pool["age"][feature_pool["age"] < 0] += 1  # 보호 프레임 감소
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
                    ages = np.full(len(added_pts), -MAX_AGE, dtype=np.int32)
                    feature_pool["age"] = np.concatenate((feature_pool["age"], ages))       # 새로운 점들도 일정 시간동안 유지
                    print(f"[{frame_idx:04d}] 🔹 Added {len(added_pts)} new points (total {len(feature_pool['pts'])})")
            else:
                print(f"[{frame_idx:04d}] ⚠️ Unable to add new features")

        else:
            print(f"[{frame_idx:04d}] Maintaining {len(feature_pool['pts'])} points")

        # === 시각화 ===
        vis_features = draw_features(frame, feature_pool["pts"], new_pts=added_pts)
        vis_flow = draw_optical_flow(frame, flow_prev, flow_next)
        combined = np.hstack((vis_features, vis_flow))

        cv2.putText(combined, f"Tracked: {len(feature_pool['pts'])}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)

        # 저장 및 표시
        out_path = os.path.join(OUTPUT_DIR, f"flow_{frame_idx:04d}.jpg")
        cv2.imwrite(out_path, combined)
        disp = cv2.resize(combined,
                          (int(combined.shape[1]*DISPLAY_SCALE),
                           int(combined.shape[0]*DISPLAY_SCALE)))
        cv2.imshow("Persistent Optical Flow (Pre-RANSAC)", disp)

        # 다음 프레임 준비
        prev_gray = gray.copy()
        frame_idx += 1

        if cv2.waitKey(10) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"✅ Optical Flow 추적 완료 (저장 위치: {OUTPUT_DIR})")


# ==========================================================
if __name__ == "__main__":
    main()
