# import cv2
# import mediapipe as mp

# mp_hands = mp.solutions.hands
# hands = mp_hands.Hands(max_num_hands=1,
#                        min_detection_confidence=0.5,
#                        min_tracking_confidence=0.5)

# def get_finger_status(hand):
#     fingers = []
#     if hand.landmark[4].x < hand.landmark[3].x:
#         fingers.append(1)
#     else:
#         fingers.append(0)

#     tips = [8, 12, 16, 20]
#     pip_joints = [6, 10, 14, 18]

#     for tip, pip in zip(tips, pip_joints):
#         if hand.landmark[tip].y < hand.landmark[pip].y:
#             fingers.append(1)
#         else:
#             fingers.append(0)
#     return fingers

# def recognize_gesture(fingers):
#     if fingers == [0, 1, 0, 0, 0]:
#         return "point"
#     return None


# class GestureToggleState:
#     """
#     글로벌 토글(ON/OFF) 상태 저장
#     """
#     def __init__(self):
#         self.service_on = False  # 초기값 OFF

# gesture_state = GestureToggleState()


# def process_gesture(frame, button_rect):
#     """
#     frame: OpenCV 이미지
#     button_rect: (x1, y1, x2, y2)
#     return:
#         "service_on_trigger", "service_off_trigger", None
#     """
#     img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     result = hands.process(img_rgb)
#     h, w, _ = frame.shape
#     x1, y1, x2, y2 = button_rect

#     if not result.multi_hand_landmarks:
#         return None

#     for hand_landmarks in result.multi_hand_landmarks:
#         fingers = get_finger_status(hand_landmarks)
#         gesture = recognize_gesture(fingers)

#         index_tip = hand_landmarks.landmark[8]
#         ix = int(index_tip.x * w)
#         iy = int(index_tip.y * h)

#         if gesture == "point":
#             inside = (x1 <= ix <= x2 and y1 <= iy <= y2)

#             if inside:
#                 # 토글 로직
#                 if not gesture_state.service_on:
#                     gesture_state.service_on = True
#                     return "service_on_trigger"
#                 else:
#                     gesture_state.service_on = False
#                     return "service_off_trigger"

#     return None
