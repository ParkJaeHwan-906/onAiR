import cv2
import numpy as np
import os
from video_loader import load_video
from feature_extractor import extract_features
from ransac_filter import ransac_filter  # ✅ RANSAC 전용 모듈

# ===== 파라미터 =====
MIN_TRACKS = 100       # Optical Flow 후 최소 유효 추적점 수
REFRESH_EVERY = 25     # 주기적 특징점 재검출 주기
DISPLAY_SCALE = 0.8    # 시각화 축소 비율


def main():
    # 🎥 영상 불러오기
    video = load_video("../data/3.mp4")

    # === 출력 디렉토리 설정 ===
    base_output = "../output"
    feature_dir = os.path.join(base_output, "features")
    flow_dir    = os.path.join(base_output, "optical_flow")
    ransac_dir  = os.path.join(base_output, "ransac")

    os.makedirs(feature_dir, exist_ok=True)
    os.makedirs(flow_dir,    exist_ok=True)
    os.makedirs(ransac_dir,  exist_ok=True)

    print("🎬 특징점 추출 → Optical Flow → RANSAC 필터링 시작")

    # === 첫 프레임 ===
    ret, prev_frame = video.read()
    if not ret:
        print("❌ 첫 프레임 읽기 실패")
        return

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_pts  = extract_features(prev_gray)
    frame_idx = 0

    while True:
        ret, frame = video.read()
        if not ret:
            print("✅ 모든 프레임 처리 완료")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        # === (1) 특징점 리프레시 ===
        if REFRESH_EVERY and frame_idx % REFRESH_EVERY == 0 and frame_idx > 0:
            prev_pts = extract_features(prev_gray)

        feature_vis = frame.copy()
        if prev_pts is not None:
            for p in prev_pts:
                x, y = p.ravel()
                cv2.circle(feature_vis, (int(x), int(y)), 2, (0, 255, 0), -1)

        # === (2) Optical Flow ===
        flow_vis = frame.copy()
        if prev_pts is not None and len(prev_pts) > 0:
            next_pts, status, err = cv2.calcOpticalFlowPyrLK(
                prev_gray, gray, prev_pts, None,
                winSize=(21, 21), maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
            )

            if next_pts is not None and status is not None:
                good_new = next_pts[status.flatten() == 1]
                good_old = prev_pts[status.flatten() == 1]

                mask = np.zeros_like(frame)
                for (new, old) in zip(good_new, good_old):
                    a, b = new.ravel(); c, d = old.ravel()
                    cv2.line(mask, (int(a), int(b)), (int(c), int(d)), (0, 255, 0), 1)
                    cv2.circle(frame, (int(a), int(b)), 2, (0, 0, 255), -1)
                flow_vis = cv2.add(frame, mask)

                if len(good_new) < MIN_TRACKS:
                    prev_pts = extract_features(gray)
                    continue

                # === (3) RANSAC 필터링 ===
                inlier_prev, inlier_next, mask_r, F = ransac_filter(
                    good_old, good_new, method="fundamental"
                )

                ransac_vis = frame.copy()
                if mask_r is not None:
                    for (new, old, ok) in zip(good_new, good_old, mask_r):
                        a, b = new.ravel(); c, d = old.ravel()
                        color = (0, 255, 0) if ok else (0, 0, 255)
                        cv2.line(ransac_vis, (int(a), int(b)), (int(c), int(d)), color, 1)
                        cv2.circle(ransac_vis, (int(a), int(b)), 2, color, -1)
                    cv2.putText(ransac_vis, f"Inliers: {np.sum(mask_r)}/{len(mask_r)}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
                else:
                    ransac_vis = frame.copy()
            else:
                print("⚠️ Optical Flow 실패 — 특징점 재검출")
                prev_pts = extract_features(gray)
                continue
        else:
            prev_pts = extract_features(gray)
            ransac_vis = frame.copy()

        # === (4) 결과 저장 ===
        cv2.imwrite(os.path.join(feature_dir, f"feature_{frame_idx:05d}.jpg"), feature_vis)
        cv2.imwrite(os.path.join(flow_dir,    f"flow_{frame_idx:05d}.jpg"), flow_vis)
        cv2.imwrite(os.path.join(ransac_dir,  f"ransac_{frame_idx:05d}.jpg"), ransac_vis)

        # === (5) 시각화 ===
        disp1 = cv2.resize(feature_vis, (int(w * DISPLAY_SCALE), int(h * DISPLAY_SCALE)))
        disp2 = cv2.resize(flow_vis,    (int(w * DISPLAY_SCALE), int(h * DISPLAY_SCALE)))
        disp3 = cv2.resize(ransac_vis,  (int(w * DISPLAY_SCALE), int(h * DISPLAY_SCALE)))

        cv2.imshow("Feature Points", disp1)
        cv2.imshow("Optical Flow",  disp2)
        cv2.imshow("RANSAC Filter", disp3)

        if cv2.waitKey(20) & 0xFF in (ord('q'), 27):
            break

        prev_gray = gray.copy()
        frame_idx += 1

    video.release()
    cv2.destroyAllWindows()

    print(f"\n💾 총 {frame_idx}개 프레임 저장 완료:")
    print(f"  - 특징점 시각화: {feature_dir}")
    print(f"  - Optical Flow : {flow_dir}")
    print(f"  - RANSAC 결과 : {ransac_dir}")


if __name__ == "__main__":
    main()
