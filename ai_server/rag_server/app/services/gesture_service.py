import cv2
import mediapipe as mp

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

def get_finger_status(hand):
    fingers = []
    # 엄지
    if hand.landmark[4].x < hand.landmark[3].x:
        fingers.append(1)
    else:
        fingers.append(0)

    # 나머지 4개 손가락
    tips = [8, 12, 16, 20]
    pip_joints = [6, 10, 14, 18]
    for tip, pip in zip(tips, pip_joints):
        if hand.landmark[tip].y < hand.landmark[pip].y:
            fingers.append(1)
        else:
            fingers.append(0)

    return fingers


def recognize_gesture(fingers):
    # 손가락 배열이 [엄지, 검지, 중지, 약지, 새끼]
    if fingers == [0, 1, 0, 0, 0]:
        return "point"
    return None


def process_gesture(frame, button_rect):
    f"""
    return:
        {
            "gesture": "point",
            "x": ix,
            "y": iy,
            "is_end_button": True/False
        }
        또는 None
    """
    try:
        if frame is None or frame.size == 0:
            return None

        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(img_rgb)

        if not result.multi_hand_landmarks:
            return None

        h, w, _ = frame.shape
        x1, y1, x2, y2 = button_rect

        SERVICE_END_BUTTON_RECT = (1800, 90, 1950, 240)
        is_button = (x1, y1, x2, y2) == SERVICE_END_BUTTON_RECT

        for hand_landmarks in result.multi_hand_landmarks:
            fingers = get_finger_status(hand_landmarks)
            gesture = recognize_gesture(fingers)

            if gesture != "point":
                continue

            # 검지 손가락 좌표
            index_tip = hand_landmarks.landmark[8]
            ix = int(index_tip.x * w)
            iy = int(index_tip.y * h)

            return {
                "gesture": "point",
                "x": ix,
                "y": iy,
                "is_end_button": is_button
            }

        return None
    
    except Exception:
        return None