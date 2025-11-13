import cv2
import numpy as np
from typing import List

def calc_sharpness(frame: np.ndarray) -> float:
    """Laplacian variance 기반 선명도 계산"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def select_sharpest_frame(frames: List[np.ndarray]) -> np.ndarray:
    """여러 프레임 중 가장 선명한 한 장 선택 (Laplacian variance 가장 큰 값)"""
    if not frames:
        raise ValueError("프레임 목록이 비어 있습니다.")
    sharpness_scores = [calc_sharpness(f) for f in frames]
    max_idx = int(np.argmax(sharpness_scores))
    return frames[max_idx]
