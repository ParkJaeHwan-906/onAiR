import cv2
import sys
import os
import time
import numpy as np

# 모듈 임포트 경로 설정 (기존 코드 유지)
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from video_loader import load_video # 이 함수는 아래에 정의된 load_video와 충돌할 수 있으니 주의 필요
from feature_extractor import FeatureExtractor
from visualizer import draw_keypoints, show_image # show_image는 사용하지 않으므로 제거하거나 주석 처리할 수 있습니다.

def process_video_and_save(video, extractor, output_dir="output_frames"):
    """
    주어진 VideoCapture 객체에서 프레임을 읽어 특징점을 추출하고,
    화면에 표시하면서 결과를 지정된 디렉토리에 저장합니다.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"출력 디렉토리 '{output_dir}'를 생성했습니다.")

    print(f"동영상 파일 처리를 시작합니다. 'q' 키를 누르면 종료됩니다.")
    
    t_prev = 0.0 # FPS 계산을 위한 시간 변수
    frame_count = 0 # 프레임 번호 카운터

    while True:
        ret, frame = video.read()

        if not ret:
            print("동영상 재생이 완료되었습니다. 종료합니다.")
            break

        keypoints, _ = extractor.extract(frame)
        
        frame_with_kps = draw_keypoints(frame.copy(), keypoints)
        
        current_time = time.time()
        fps = 1 / (current_time - t_prev) if current_time > t_prev else 0
        t_prev = current_time
        
        cv2.putText(frame_with_kps, f'FPS: {int(fps)}', (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        file_name = os.path.join(output_dir, f"frame_{frame_count:05d}.jpg")
        cv2.imwrite(file_name, frame_with_kps)
        
        cv2.imshow('ORB Feature Tracking', frame_with_kps)

        frame_count += 1
        if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
            print("사용자 요청으로 종료합니다.")
            break

    # 4. 자원 해제
    video.release()
    cv2.destroyAllWindows()
    print(f"총 {frame_count}개의 이미지를 '{output_dir}'에 저장했습니다.")


def main():
    try:
        # load_video(1)로 비디오 캡처 객체 로드
        video = load_video(1) 
    except FileNotFoundError as e:
        print("Video Not Found.")
        return
    
    # 특징점 추출기 초기화
    extractor = FeatureExtractor(nfeatures=500)
    
    # 분리된 함수 호출, output_frames 디렉토리에 저장
    process_video_and_save(video, extractor, output_dir="output_frames")


if __name__ == "__main__":
    main()