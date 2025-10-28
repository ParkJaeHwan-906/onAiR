import cv2
import os

def load_video(idx):
    path = f"../data/{idx}.mp4"
    video = cv2.VideoCapture(path)
    if not video.isOpened():
        raise FileNotFoundError(f"'{path}' 파일을 열 수 없습니다.")
    
    actual_fps = video.get(cv2.CAP_PROP_FPS)
    total_frames = video.get(cv2.CAP_PROP_FRAME_COUNT)

    print(f"실제 동영상 파일의 FPS: {actual_fps}")
    print(f"실제 동영상 파일의 총 프레임 수 (메타데이터): {total_frames}")
    return video