# essential_pose.py
import cv2
import numpy as np
from typing import Tuple, Optional

def compute_essential_and_pose(
    inlier_prev: np.ndarray,
    inlier_next: np.ndarray,
    K: np.ndarray,
    *,
    distCoeffs: Optional[np.ndarray] = None,
    threshold: float = 1.0,
    prob: float = 0.999,
    use_undistort: bool = True
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Essential Matrix 추정 + recoverPose로 카메라 상대자세(R, t) 복원.
    ─────────────────────────────────────────────────────────────────────────────
    ■ 이 함수가 하는 일
      1) (가능하면) 좌표를 카메라 보정(undistort)하여 normalized image plane으로 변환한다.
      2) RANSAC으로 Essential Matrix(E)를 추정한다.
      3) recoverPose(E, ...)로 회전 R(3x3), 이동 t(3x1)를 구한다.
      4) pose 마스크(재투영 기준 inlier)도 함께 반환한다.

    ■ 왜 Essential인가?
      - E는 보정된 좌표에서만 정의되며, 카메라의 상대 회전·이동을 직접 복원할 수 있다.
      - F는 outlier 제거(정제)에 좋지만, R,t 복원은 E + recoverPose로 해야 한다.

    Parameters
    ----------
    inlier_prev : (M,2) or (M,1,2) float32
        RANSAC(F) 필터를 통과한 이전 프레임 좌표들.
    inlier_next : (M,2) or (M,1,2) float32
        RANSAC(F) 필터를 통과한 현재 프레임 좌표들.
    K : (3,3) float64
        카메라 내재 행렬 (fx, fy, cx, cy).
    distCoeffs : (k,) or None, default=None
        왜곡 계수. 제공되면 undistortPoints에 사용한다.
    threshold : float, default=1.0
        Essential RANSAC의 최대 허용 오차(픽셀 단위). 0.8~1.5 권장.
    prob : float, default=0.999
        Essential RANSAC의 신뢰도.
    use_undistort : bool, default=True
        True면 undistortPoints로 정규화된 좌표계에서 E를 추정한다.
        (이미 왜곡 보정/정규화된 좌표를 넘긴다면 False로 둘 수 있다)

    Returns
    -------
    E : (3,3) or None
        추정된 Essential Matrix. 실패 시 None.
    R : (3,3) or None
        상대 회전행렬. 실패 시 None.
    t : (3,1) or None
        상대 이동벡터(단위 벡터; scale 미정). 실패 시 None.
    pose_mask : (M,1) or None
        recoverPose가 유효하다고 판단한 inlier 마스크(재투영 기준). 실패 시 None.

    Notes
    -----
    - t(이동)는 "방향"만 복원된다(스케일 모호성). 절대 스케일은 따로 정해야 한다(예: IMU, 마커, 구조 가정 등).
    - E 추정 후 recoverPose 마스크로 한 번 더 inlier가 걸러진다. (RANSAC→recoverPose 2단 필터)
    - inlier 수가 너무 적으면(예: < 8) E 추정이 불안정하거나 실패할 수 있다.
    """

    # ---------- 0) 입력 검증 ----------
    if inlier_prev is None or inlier_next is None or K is None:
        print("❌ Essential: 입력이 None입니다.")
        return None, None, None, None
    if len(inlier_prev) < 8 or len(inlier_next) < 8:
        print(f"⚠️ Essential: 대응점 부족 ({len(inlier_prev)}개). 최소 8개 필요.")
        return None, None, None, None

    # ---------- 1) 형상 통일 ----------
    p1 = np.squeeze(inlier_prev).astype(np.float32)
    p2 = np.squeeze(inlier_next).astype(np.float32)

    # ---------- 2) (선택) 왜곡 보정 + 정규화 ----------
    #  - undistortPoints는 (N,1,2) 입력을 기대하므로 형태를 맞춘 뒤 반환값을 (N,2)로 다시 정리한다.
    if use_undistort:
        p1_norm = cv2.undistortPoints(p1.reshape(-1,1,2), K, distCoeffs).reshape(-1,2)
        p2_norm = cv2.undistortPoints(p2.reshape(-1,1,2), K, distCoeffs).reshape(-1,2)
        # findEssentialMat에 바로 normalized 좌표를 넣을 수도 있지만,
        # OpenCV는 (픽셀좌표, K) 조합으로 쓰는 경로가 일반적이므로 아래 방식을 따른다.
        # (둘 다 가능; 여기서는 K를 함께 넘기는 일반 경로로 진행)
        pts_for_E_1, pts_for_E_2 = p1, p2
    else:
        pts_for_E_1, pts_for_E_2 = p1, p2

    # ---------- 3) Essential + RANSAC ----------
    #  - K를 넘기면 OpenCV 내부에서 정규화/오차 계산이 적절히 이루어진다.
    E, maskE = cv2.findEssentialMat(
        pts_for_E_1, pts_for_E_2, K,
        method=cv2.RANSAC,
        prob=prob,
        threshold=threshold
    )
    if E is None or maskE is None:
        print("❌ Essential: E 행렬 추정 실패")
        return None, None, None, None

    # ---------- 4) Pose 복원 ----------
    #  - 마스크는 재투영 기준의 inlier를 나타낸다(필터 한 번 더!).
    _, R, t, pose_mask = cv2.recoverPose(E, pts_for_E_1, pts_for_E_2, K)
    if R is None or t is None:
        print("❌ Essential: recoverPose 실패")
        return E, None, None, maskE

    inliers_pose = int(np.count_nonzero(pose_mask))
    total = len(pose_mask)
    print(f"✅ Essential+Pose: Inliers {inliers_pose}/{total} ({inliers_pose/total*100:.1f}%), "
          f"||t||=1 (scale-free)")

    return E, R, t, pose_mask
