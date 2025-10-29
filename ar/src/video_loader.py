import cv2
import os

def load_video(source):
    """
    비디오 캡처 객체 로드
    Parameters:
        source : int | str
            0이면 웹캠, 문자열이면 영상 파일 경로
            -> 라즈베리파이에 올릴 수 있으면 webcam 으로 쓸 수도 있지 않을까?
    Returns:
        cap : cv2.VideoCapture 객체
    """
    if isinstance(source, str) and not os.path.exists(source):
        raise FileNotFoundError(f"Video file not found: {source}")
    
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise IOError("Failed to open video source.")    
    return cap