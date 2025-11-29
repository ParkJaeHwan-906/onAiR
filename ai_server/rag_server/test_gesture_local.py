"""
로컬 웹캠을 사용한 MediaPipe 제스처 인식 테스트 스크립트

사용법:
    python test_gesture_local.py

기능:
    - 웹캠에서 영상 수신
    - MediaPipe로 손 인식
    - Point 제스처 인식 (검지만 펴고 나머지 구부림)
    - 버튼 영역 표시 및 클릭 감지
    - 좌표 정보 실시간 출력
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
from pathlib import Path
import os

# MediaPipe 설정
BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

# 모델 경로 설정
BASE_DIR = Path(__file__).parent
MODEL_PATH = str(BASE_DIR / "app" / "models" / "hand_landmarker.task")

# 테스트용 버튼 영역 (화면 중앙 오른쪽 상단)
BUTTON_RECT = (1710, 45, 1860, 195)  # (left, top, right, bottom)
# 또는 화면 크기에 맞춰 조정하려면:
# BUTTON_RECT = (800, 50, 950, 200)  # 1280x720 해상도 기준


def get_finger_status(landmarks):
    """손가락 상태 계산"""
    fingers = []
    
    # 엄지: landmark[4], landmark[3]
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    fingers.append(1 if thumb_tip.x < thumb_ip.x else 0)
    
    # 검지~소지 TIP / PIP
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    
    for tip_idx, pip_idx in zip(tips, pips):
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        fingers.append(1 if tip.y < pip.y else 0)
    
    return fingers


def recognize_gesture(fingers):
    """제스처 인식"""
    if fingers == [0, 1, 0, 0, 0]:
        return "point"
    return None


def main():
    # 모델 파일 확인
    if not os.path.exists(MODEL_PATH):
        print(f"❌ 모델 파일을 찾을 수 없습니다: {MODEL_PATH}")
        print("   hand_landmarker.task 파일이 app/models/ 디렉토리에 있는지 확인하세요.")
        return
    
    # HandLandmarker 초기화
    print("📦 MediaPipe HandLandmarker 초기화 중...")
    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.IMAGE,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = HandLandmarker.create_from_options(options)
    print("✅ 초기화 완료")
    
    # 웹캠 열기
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ 웹캠을 열 수 없습니다.")
        return
    
    # 웹캠 해상도 설정 (선택사항)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    # 실제 해상도 확인
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"📹 웹캠 해상도: {width}x{height}")
    
    # 버튼 영역이 화면 크기를 벗어나면 조정
    left, top, right, bottom = BUTTON_RECT
    if right > width or bottom > height:
        print(f"⚠️ 버튼 영역이 화면 크기를 벗어남. 화면 크기에 맞춰 조정합니다.")
        # 화면 오른쪽 상단에 버튼 배치
        button_width = 150
        button_height = 150
        left = width - button_width - 10
        top = 10
        right = width - 10
        bottom = top + button_height
        print(f"   조정된 버튼 영역: ({left}, {top}, {right}, {bottom})")
    
    print("\n" + "=" * 80)
    print("🎮 제스처 인식 테스트 시작")
    print("=" * 80)
    print("📌 사용법:")
    print("   - 검지만 펴고 나머지 손가락을 구부리면 'point' 제스처 인식")
    print("   - 검지 끝이 빨간색 버튼 영역 안에 있으면 클릭 감지")
    print("   - 'q' 키를 누르면 종료")
    print("=" * 80 + "\n")
    
    frame_count = 0
    click_detected = False
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ 프레임을 읽을 수 없습니다.")
                break
            
            frame_count += 1
            h, w, _ = frame.shape
            
            # OpenCV BGR → RGB 변환
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # MediaPipe Image 생성
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=frame_rgb
            )
            
            # 손 인식
            result = landmarker.detect(mp_image)
            
            # 버튼 영역 그리기
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.putText(frame, "Button", (left, top - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            if result.hand_landmarks:
                # 첫 번째 손만 사용
                landmarks = result.hand_landmarks[0]
                
                # 손 랜드마크 그리기
                for landmark in landmarks:
                    x = int(landmark.x * w)
                    y = int(landmark.y * h)
                    cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
                
                # 손가락 상태 계산
                fingers = get_finger_status(landmarks)
                gesture = recognize_gesture(fingers)
                
                # 검지 끝 좌표
                index_tip = landmarks[8]
                ix = int(index_tip.x * w)
                iy = int(index_tip.y * h)
                
                # 검지 끝 표시
                cv2.circle(frame, (ix, iy), 10, (255, 0, 0), -1)
                cv2.putText(frame, f"({ix}, {iy})", (ix + 15, iy), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
                # 제스처 인식 여부 표시
                if gesture == "point":
                    cv2.putText(frame, "POINT GESTURE", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    # 버튼 영역 내부 체크
                    inside = (left <= ix <= right and top <= iy <= bottom)
                    
                    if inside:
                        # 클릭 감지
                        if not click_detected:
                            click_detected = True
                            print("=" * 80)
                            print("✅ [클릭 감지]")
                            print(f"   검지 좌표: ({ix}, {iy})")
                            print(f"   버튼 영역: ({left}, {top}, {right}, {bottom})")
                            print(f"   프레임 크기: ({w}, {h})")
                            print(f"   손가락 상태: {fingers}")
                            print("=" * 80)
                        
                        # 버튼 영역 강조
                        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 3)
                        cv2.putText(frame, "CLICKED!", (left, top - 30), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    else:
                        click_detected = False
                else:
                    click_detected = False
                    # 손가락 상태 표시
                    cv2.putText(frame, f"Fingers: {fingers}", (10, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            else:
                click_detected = False
            
            # 프레임 정보 표시
            cv2.putText(frame, f"Frame: {frame_count}", (10, h - 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Size: {w}x{h}", (10, h - 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # 화면에 표시
            cv2.imshow("Gesture Test - Press 'q' to quit", frame)
            
            # 'q' 키로 종료
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\n✅ 테스트 종료")


if __name__ == "__main__":
    main()

