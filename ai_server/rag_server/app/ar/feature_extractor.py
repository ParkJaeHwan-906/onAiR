import cv2
import numpy as np

def extract_features(gray_frame, max_corners=1200, quality=0.08, min_distance=6):
    """
    안정형 특징점 추출기 (GFTT ↔ ORB 자동 선택)
    - CLAHE 명암보정
    - Laplacian 평탄도 검사
    - 저대비 장면에서는 ORB fallback
    - GFTT일 때만 sub-pixel refinement
    - 현재 사용된 방법(method)도 함께 반환
    """

    if gray_frame is None or gray_frame.size == 0:
        return np.array([]), "NONE"

    # === ① CLAHE 명암 보정 ===
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray_frame)

    # === ② Laplacian variance 계산 ===
    lap_var = cv2.Laplacian(enhanced, cv2.CV_64F).var()
    low_contrast = lap_var < 10

    # === ③ 알고리즘 선택 ===
    if not low_contrast:
        # ✅ 충분히 명암 있는 장면 → GFTT 사용
        points = cv2.goodFeaturesToTrack(
            enhanced,
            maxCorners=max_corners,
            qualityLevel=quality,
            minDistance=min_distance,
            blockSize=7
        )
        method = "GFTT"
    else:
        # ⚠️ 저대비 장면 → ORB fallback
        orb = cv2.ORB_create(
            nfeatures=max_corners,
            scaleFactor=1.2,
            nlevels=8,
            edgeThreshold=15,
            patchSize=31
        )
        keypoints = orb.detect(enhanced, None)
        points = np.array([kp.pt for kp in keypoints], dtype=np.float32).reshape(-1, 1, 2)
        method = "ORB"
        print(f"⚠️ Low contrast scene (Var={lap_var:.2f}) — using ORB fallback ({len(points)} pts)")

    # === ④ 결과 검증 ===
    if points is None or len(points) == 0:
        return np.array([]), method

    # === ⑤ Sub-pixel refinement (GFTT 전용) ===
    if method == "GFTT":
        term_crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        cv2.cornerSubPix(enhanced, points, (5, 5), (-1, -1), term_crit)

    return points.reshape(-1, 1, 2).astype(np.float32), method
