import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
import time
import os
from pathlib import Path

BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
HandLandmarkerResult = mp.tasks.vision.HandLandmarkerResult
VisionRunningMode = mp.tasks.vision.RunningMode

# 모델 경로 설정 (__file__ 기반 절대 경로)
BASE_DIR = Path(__file__).parent.parent.parent  # app/services -> app -> rag_server
MODEL_PATH = str(BASE_DIR / "app" / "models" / "hand_landmarker.task")

# Landmarker 지연 초기화 (모듈 로드 시점이 아닌 사용 시점에 초기화)
landmarker = None

def _get_landmarker():
    """Landmarker 싱글톤 패턴 (지연 초기화)"""
    global landmarker
    if landmarker is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"MediaPipe 모델 파일을 찾을 수 없습니다: {MODEL_PATH}")
        
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=VisionRunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        landmarker = HandLandmarker.create_from_options(options)
    return landmarker


def get_finger_status(landmarks):
    """
    landmarks = result.hand_landmarks[0] (21개 좌표)
    """
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
    if fingers == [0, 1, 0, 0, 0]:
        return "point"
    return None


def process_gesture(frame, button_rect):
    """
    return:
        {
            "gesture": "point",
            "x": ix,
            "y": iy,
            "is_end_button": True/False
        }
    """

    try:
        if frame is None or frame.size == 0:
            return None

        h, w, _ = frame.shape

        # OpenCV BGR → RGB 변환 (MediaPipe는 RGB를 기대)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # MediaPipe는 contiguous array를 요구하므로 메모리 레이아웃 확인 및 수정
        if not frame_rgb.flags['C_CONTIGUOUS']:
            frame_rgb = np.ascontiguousarray(frame_rgb)

        # OpenCV -> MediaPipe Image
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=frame_rgb
        )

        # Landmarker 지연 초기화 및 동기식 처리
        landmarker = _get_landmarker()
        result = landmarker.detect(mp_image)

        # 손 인식 여부 확인 로그 (주기적으로 출력)
        if not hasattr(process_gesture, '_hand_detection_log_count'):
            process_gesture._hand_detection_log_count = 0
        process_gesture._hand_detection_log_count += 1
        
        if not result.hand_landmarks:
            # 100프레임마다 손 인식 실패 로그 출력
            if process_gesture._hand_detection_log_count % 100 == 0:
                print(f"🔍 [Gesture] 손 인식 실패 (총 {process_gesture._hand_detection_log_count}회 시도)")
            return None
        
        # 손 인식 성공 시 로그 출력 (처음 몇 번만)
        if not hasattr(process_gesture, '_hand_detected_logged'):
            process_gesture._hand_detected_logged = False
        if not process_gesture._hand_detected_logged:
            print(f"✅ [Gesture] 손 인식 성공! hand_landmarks 개수: {len(result.hand_landmarks)}")
            process_gesture._hand_detected_logged = True

        x1, y1, x2, y2 = button_rect
        # is_end_button은 현재 사용하지 않으므로 False로 설정
        # (gesture_state.py에서 button_rect를 직접 비교하므로 불필요)
        is_end_button = False

        # 첫 번째 손만 사용
        landmarks = result.hand_landmarks[0]
        fingers = get_finger_status(landmarks)
        gesture = recognize_gesture(fingers)

        # 디버깅: 제스처 인식 상태 출력
        if gesture != "point":
            # 주석 처리: 너무 많은 로그 방지
            # print(f"🔍 [Gesture Debug] 제스처 미인식 - fingers: {fingers}, gesture: {gesture}")
            return None

        # 검지 끝
        index_tip = landmarks[8]
        ix = int(index_tip.x * w)
        iy = int(index_tip.y * h)

        # 디버깅: 제스처 인식 성공 시 좌표 출력 (주석 처리: 너무 많은 로그 방지)
        # print(f"🔍 [Gesture Debug] 제스처 인식 성공 - 검지 좌표: ({ix}, {iy}), 프레임 크기: ({w}, {h}), MediaPipe 좌표: ({index_tip.x:.3f}, {index_tip.y:.3f})")

        return {
            "gesture": "point",
            "x": ix,
            "y": iy,
            "is_end_button": is_end_button,
        }

    except Exception as e:
        print(f"[GestureService ERROR] {e}")
        return None
    