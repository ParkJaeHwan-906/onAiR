## 일단 재환이가 프레임 내의 클릭버튼 위치 좌표 고정해주면 그걸로 바꾸기
## 나영 언니한테 작업자가 on 용으로 이 제스처&버튼을 활용할 거니까 on 하는 시점 외에는 이 버튼을 비활성화했다가 서비스 다 종료되거나면 다시 활성화하는 방법 논의하기

import cv2
import mediapipe as mp

# Mediapipe 설정
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, 
                       min_detection_confidence=0.5, 
                       min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils


def get_finger_status(hand):
    fingers = []

    # 엄지 판단
    if hand.landmark[4].x < hand.landmark[3].x:
        fingers.append(1)
    else:
        fingers.append(0)

    # 나머지 손가락 TIP / PIP 비교
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
        return 'point'
    return None


# 버튼 영역 설정 (좌측 상단)
button_x1, button_y1 = 20, 20
button_x2, button_y2 = 170, 120


video = cv2.VideoCapture(0)
print("Running... ESC to exit")

while video.isOpened():
    ret, frame = video.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(img_rgb)

    # 버튼 UI 그리기
    cv2.rectangle(frame, (button_x1, button_y1), (button_x2, button_y2),
                  (0, 255, 0), 2)
    cv2.putText(frame, "CLICK", (button_x1 + 20, button_y1 + 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    clicked = False

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            fingers_status = get_finger_status(hand_landmarks)
            gesture = recognize_gesture(fingers_status)

            # index finger tip
            index_tip = hand_landmarks.landmark[8]  # 8번 인덱스
            ix, iy = int(index_tip.x * w), int(index_tip.y * h)

            # 손가락 점 찍기
            cv2.circle(frame, (ix, iy), 8, (0, 0, 255), -1)

            # 버튼 내부에 손가락 들어갔는지
            if gesture == "point":
                if button_x1 <= ix <= button_x2 and button_y1 <= iy <= button_y2:
                    clicked = True

            mp_drawing.draw_landmarks(
                frame, hand_landmarks, mp_hands.HAND_CONNECTIONS
            )

    # 클릭되면 버튼을 빨간색으로 강조
    if clicked:
        cv2.rectangle(frame, (button_x1, button_y1), (button_x2, button_y2),
                      (0, 0, 255), 3)
        cv2.putText(frame, "CLICKED!", (button_x1 + 10, button_y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        print("Button CLICKED!")

    cv2.imshow("Gesture Button Demo", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

video.release()
cv2.destroyAllWindows()
