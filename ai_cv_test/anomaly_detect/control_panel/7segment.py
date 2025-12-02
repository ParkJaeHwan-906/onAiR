import cv2
import numpy as np

# -----------------------
# 7-Segment Pattern Map
# -----------------------
SEGMENT_MAP = {
    (1,1,1,1,1,1,0): "0",
    (0,1,1,0,0,0,0): "1",
    (1,1,0,1,1,0,1): "2",
    (1,1,1,1,0,0,1): "3",
    (0,1,1,0,0,1,1): "4",
    (1,0,1,1,0,1,1): "5",
    (1,0,1,1,1,1,1): "6",
    (1,1,1,0,0,0,0): "7",
    (1,1,1,1,1,1,1): "8",
    (1,1,1,1,0,1,1): "9",
}

# -----------------------
# Segment ON/OFF Detector
# -----------------------
def get_segment_states(digit_img):
    h, w = digit_img.shape

    # 각 segment별 Zone 정의
    segment_zones = {
        0: digit_img[0:int(0.20*h), int(0.20*w):int(0.80*w)],                # Top
        1: digit_img[int(0.15*h):int(0.50*h), int(0.70*w):w],               # Top-right
        2: digit_img[int(0.55*h):int(0.90*h), int(0.70*w):w],               # Bottom-right
        3: digit_img[int(0.80*h):h, int(0.20*w):int(0.80*w)],               # Bottom
        4: digit_img[int(0.55*h):int(0.90*h), 0:int(0.30*w)],               # Bottom-left
        5: digit_img[int(0.15*h):int(0.50*h), 0:int(0.30*w)],               # Top-left
        6: digit_img[int(0.40*h):int(0.60*h), int(0.20*w):int(0.80*w)],     # Middle
    }

    states = []

    for i in range(7):
        zone = segment_zones[i]
        # 흰색 픽셀 비율
        white_ratio = np.sum(zone > 0) / zone.size

        # 0.25 이상 흰색이면 ON
        states.append(1 if white_ratio > 0.20 else 0)

    return tuple(states)

# -----------------------
# Digit Recognition
# -----------------------
def recognize_digit(digit_img):
    states = get_segment_states(digit_img)
    return SEGMENT_MAP.get(states, "?")

# -----------------------
# 전체 숫자 판독
# -----------------------
def recognize_digits_from_mask(mask_img):
    # Contour로 digit 분리
    contours, _ = cv2.findContours(mask_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    digit_boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w*h < 200:   # 작은 노이즈 제외
            continue
        digit_boxes.append((x,y,w,h))

    # left-to-right 정렬
    digit_boxes = sorted(digit_boxes, key=lambda b: b[0])

    result = ""
    for (x,y,w,h) in digit_boxes:
        digit_roi = mask_img[y:y+h, x:x+w]
        digit = recognize_digit(digit_roi)
        result += digit

    return result

# -----------------------
# 실행 예시
# -----------------------
if __name__ == "__main__":
    mask = cv2.imread("debug_display_mask.png", cv2.IMREAD_GRAYSCALE)

    value = recognize_digits_from_mask(mask)
    print("🔍 인식된 숫자:", value)
