import cv2
import numpy as np

def extract_features(gray_frame, max_corners=500, quality=0.01, min_distance=30):
    """
    Shi-Tomasi 코너 기반 특징점 추출
    Parameters:
        gray_frame : np.ndarray
            입력 그레이스케일 이미지
        max_corners : int
            검출할 최대 특징점 개수
        quality : float
            특징점의 최소 품질 수준 (0~1 사이)
        min_distance : int
            두 특징점 간 최소 거리 (픽셀 단위)
    Returns:
        points : np.ndarray (N, 1, 2)
            검출된 특징점 좌표 목록
    """
    points = cv2.goodFeaturesToTrack(
        gray_frame,
        maxCorners=max_corners,
        qualityLevel=quality,
        minDistance=min_distance
    )
    if points is None:
        return np.array([])
    return points.reshape(-1, 1, 2).astype(np.float32)
