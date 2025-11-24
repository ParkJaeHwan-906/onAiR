import cv2
import mediapipe as mp

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1,
                       min_detection_confidence=0.5,
                       min_tracking_confidence=0.5)

def get_finger_status(hand):
    fingers = []
    if hand.landmark[4].x < hand.landmark[3].x:
        fingers.append(1)
    else:
        fingers.append(0)

    tips = [8, 12, 16, 20]
    pip_joints = [6, 10, 14, 18]

    for tip, pip in zip(tips, pip_joints):
        if hand.landmark[tip].y < hand.landmark[pip].y:
            fingers.append(1)
        else:
            fingers.append(0)
    return fingers

def recognize_gesture(fingers):
    if fingers == [0, 1, 0, 0, 0]:
        return "point"
    return None


class GestureToggleState:
    """
    글로벌 토글(ON/OFF) 상태 저장
    """
    def __init__(self):
        self.service_on = False  # 초기값 OFF

gesture_state = GestureToggleState()


def process_gesture(frame, button_rect):
    """
    frame: OpenCV 이미지
    button_rect: (x1, y1, x2, y2)
    return:
        "service_on_trigger", "service_off_trigger", "service_end_button_clicked", None
    """
    try:
        if frame is None or frame.size == 0:
            return None
        
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(img_rgb)
    h, w, _ = frame.shape
    x1, y1, x2, y2 = button_rect

    if not result.multi_hand_landmarks:
        return None

        # 서비스 종료 버튼 좌표 (left=1800, top=90, right=1950, bottom=240)
        SERVICE_END_BUTTON_RECT = (1800, 90, 1950, 240)
        is_service_end_button = (x1, y1, x2, y2) == SERVICE_END_BUTTON_RECT

    for hand_landmarks in result.multi_hand_landmarks:
        fingers = get_finger_status(hand_landmarks)
        gesture = recognize_gesture(fingers)

        index_tip = hand_landmarks.landmark[8]
        ix = int(index_tip.x * w)
        iy = int(index_tip.y * h)

        if gesture == "point":
            inside = (x1 <= ix <= x2 and y1 <= iy <= y2)

            if inside:
                    # 서비스 종료 버튼인 경우
                    if is_service_end_button:
                        return "service_end_button_clicked"
                    
                    # 기존 토글 로직 (다른 버튼용)
                if not gesture_state.service_on:
                    gesture_state.service_on = True
                    return "service_on_trigger"
                else:
                    gesture_state.service_on = False
                    return "service_off_trigger"

    return None
    except Exception as e:
        # mediapipe 처리 중 오류 발생 시 조용히 None 반환 (비디오 프레임 처리 중단 방지)
        return None
