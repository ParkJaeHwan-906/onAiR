import cv2
import numpy as np
import os
from video_loader import load_video
from feature_extractor import extract_features
from motion_estimator import estimate_motion_ransac  # ✅ RANSAC+Pose

# 튜닝 파라미터
MIN_TRACKS   = 120   # Optical Flow 후 최소 유효 추적점 수
MIN_INLIERS  = 60    # RANSAC 인라이어 최소 수
REFRESH_EVERY = 20   # 주기적 리프레시(프레임 수 기준), 0이면 비활성

def main():
    video = load_video("../data/3.mp4")
    K = np.load("../data/camera_intrinsics.npy")

    # 출력 폴더
    base_output = "../output"
    feature_dir = os.path.join(base_output, "features")
    flow_dir    = os.path.join(base_output, "optical_flow")
    ransac_dir  = os.path.join(base_output, "ransac")
    os.makedirs(feature_dir, exist_ok=True)
    os.makedirs(flow_dir,    exist_ok=True)
    os.makedirs(ransac_dir,  exist_ok=True)

    frame_idx = 0
    print("🎬 Optical Flow + RANSAC 기반 추적 시작")

    ret, prev_frame = video.read()
    if not ret:
        print("❌ 첫 프레임 읽기 실패")
        return

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_pts  = extract_features(prev_gray)  # 첫 프레임 특징점

    while True:
        ret, frame = video.read()
        if not ret:
            print("✅ 모든 프레임 처리 완료")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # (옵션) 주기적 리프레시: 오래 추적하면 품질 저하 → 주기적으로 재검출
        if REFRESH_EVERY and frame_idx % REFRESH_EVERY == 0 and frame_idx > 0:
            prev_pts = extract_features(prev_gray)

        # 1) 특징점 시각화(항상 저장 가능하도록 미리 만들어둠)
        feature_vis = frame.copy()
        if prev_pts is not None and len(prev_pts) > 0:
            for p in prev_pts:
                x, y = p.ravel()
                cv2.circle(feature_vis, (int(x), int(y)), 2, (0, 255, 0), -1)

        # 기본 출력 초기화 (실패 케이스 대비)
        flow_vis   = frame.copy()
        ransac_vis = frame.copy()

        # 2) Optical Flow
        need_redetect = False
        if prev_pts is None or len(prev_pts) == 0:
            need_redetect = True
        else:
            next_pts, status, err = cv2.calcOpticalFlowPyrLK(
                prev_gray, gray, prev_pts, None,
                winSize=(21, 21), maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
            )

            # (A) LK 실패 처리
            if next_pts is None or status is None:
                need_redetect = True
            else:
                good_new = next_pts[status.flatten() == 1]
                good_old = prev_pts[status.flatten() == 1]

                # Optical Flow 시각화(이전→현재 한 프레임만)
                mask = np.zeros_like(frame)
                for (new, old) in zip(good_new, good_old):
                    a, b = new.ravel(); c, d = old.ravel()
                    cv2.line(mask, (int(a), int(b)), (int(c), int(d)), (0, 255, 0), 1)
                    cv2.circle(frame, (int(a), int(b)), 2, (0, 0, 255), -1)
                flow_vis = cv2.add(frame, mask)

                # (B) 유효 추적점 수 체크
                if len(good_new) < MIN_TRACKS:
                    need_redetect = True
                else:
                    # 3) RANSAC + Pose
                    R, t, inlier_mask, E = estimate_motion_ransac(good_old, good_new, K)

                    if inlier_mask is not None:
                        # 인라이어/아웃라이어 시각화
                        ransac_vis = frame.copy()
                        inlier_cnt = int(np.sum(inlier_mask))
                        for (new, old, ok) in zip(good_new, good_old, inlier_mask):
                            a, b = new.ravel(); c, d = old.ravel()
                            color = (0, 255, 0) if ok else (0, 0, 255)
                            cv2.line(ransac_vis, (int(a), int(b)), (int(c), int(d)), color, 1)
                            cv2.circle(ransac_vis, (int(a), int(b)), 2, color, -1)

                        cv2.putText(ransac_vis, f"Inliers: {inlier_cnt}/{len(inlier_mask)}",
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
                        cv2.putText(ransac_vis, f"t: {np.round(t.flatten()[:3],3)}",
                                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)

                        # (C) 인라이어 수 부족 시 재검출
                        if inlier_cnt < MIN_INLIERS:
                            need_redetect = True
                            # 다음 루프에서 새 점으로 시작하도록 flow_vis/ransac_vis는 그대로 둠

                        # 다음 루프용 포인트: 인라이어만 쓰면 더 안정적
                        prev_pts = good_new[inlier_mask].reshape(-1, 1, 2)
                    else:
                        # RANSAC 실패 → 재검출
                        need_redetect = True

        # 4) 재검출 처리
        if need_redetect:
            prev_pts = extract_features(gray)
            # 재검출 장면도 feature_vis로 보이도록 갱신
            feature_vis = frame.copy()
            if prev_pts is not None and len(prev_pts) > 0:
                for p in prev_pts:
                    x, y = p.ravel()
                    cv2.circle(feature_vis, (int(x), int(y)), 2, (0, 255, 0), -1)

        # 5) 저장
        feature_path = os.path.join(feature_dir, f"feature_{frame_idx:05d}.jpg")
        flow_path    = os.path.join(flow_dir,    f"flow_{frame_idx:05d}.jpg")
        ransac_path  = os.path.join(ransac_dir,  f"ransac_{frame_idx:05d}.jpg")
        cv2.imwrite(feature_path, feature_vis)
        cv2.imwrite(flow_path,    flow_vis)
        cv2.imwrite(ransac_path,  ransac_vis)

        # 6) 뷰
        cv2.imshow("Feature Points", feature_vis)
        cv2.imshow("Optical Flow",  flow_vis)
        cv2.imshow("RANSAC",        ransac_vis)
        if cv2.waitKey(30) & 0xFF in (ord('q'), 27):
            break

        prev_gray = gray.copy()
        frame_idx += 1

    video.release()
    cv2.destroyAllWindows()
    print(f"💾 총 {frame_idx}개 프레임 저장 완료:")
    print(f"  - 특징점 시각화: {feature_dir}")
    print(f"  - Optical Flow: {flow_dir}")
    print(f"  - RANSAC 결과:  {ransac_dir}")

if __name__ == "__main__":
    main()
