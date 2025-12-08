import cv2
import numpy as np
import pytesseract
from ultralytics import YOLO
import re

MODULE_MODEL_PATH = "../../AHU-module-detection/runs/train/module_yolo11n/weights/best.pt"
PANEL_MODEL_PATH = "../../control-panel-8/runs/train/panel_yolo11n/weights/best.pt"
IMAGE_PATH = "./origin/control_panel6.jpg"


# ----------------------------
# 0. 대비 강화 함수들
# ----------------------------
def enhance_contrast_led(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # 감마보정 완화
    gamma = 1.3
    v = np.clip((v / 255.0) ** (1 / gamma) * 255.0, 0, 255).astype(np.uint8)

    enhanced_hsv = cv2.merge([h, s, v])
    return cv2.cvtColor(enhanced_hsv, cv2.COLOR_HSV2BGR)

def boost_red(img):
    b, g, r = cv2.split(img)
    # 과한 강조 방지 (1.2~1.3 정도)
    r = cv2.addWeighted(r, 1.3, np.zeros_like(r), 0, 0)
    boosted = cv2.merge([b, g, np.clip(r, 0, 255).astype(np.uint8)])
    return boosted


# ----------------------------
# 1. 온도 탐지 함수 (OCR 개선)
# ----------------------------
def ocr_temperature(img):
    import re

    # 1) 중앙부만 크롭 (테두리/아이콘 제외)
    h, w = img.shape[:2]
    crop = img[int(h * 0.15):int(h * 0.85), int(w * 0.15):int(w * 0.85)]

    # 2) 그레이 + 가벼운 블러
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # 3) 자동 이진화 두 가지(정/역) 모두 준비
    _, th_bin = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    _, th_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    # 4) 두 이미지 중 "흰색 비율이 1~40% 사이"에 가까운 쪽 선택 (숫자만 적절히 남는 쪽)
    def choose(th):
        ratio = (th == 255).mean()
        return abs(ratio - 0.20), ratio  # 20% 목표
    c1, r1 = choose(th_bin)
    c2, r2 = choose(th_inv)
    thresh = th_bin if c1 <= c2 else th_inv

    # 5) 아주 약한 형태 보정(작은 잡점만 제거). 점(.) 살리려고 커널 1x1~2x1만 사용
    kernel = np.ones((1, 2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    # 디버그 저장
    cv2.imwrite("temp_roi_debug.jpg", crop)
    cv2.imwrite("temp_thresh_debug.jpg", thresh)

    # 6) Tesseract 두 가지 PSM 시도: 8(단어) → 7(한 줄)
    def run_ocr(img_bin):
        for psm in (8, 7):
            cfg = f"--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789."
            txt = pytesseract.image_to_string(img_bin, config=cfg).strip()
            # 1차: 12.3 형태
            m = re.search(r"\d+\.\d+", txt)
            if m:
                return float(m.group())
            # 2차: 123 형태 → 소수점 보정(끝에서 한 자리 앞)
            ds = re.findall(r"\d", txt)
            if len(ds) >= 3:
                val = float("".join(ds[:-1]) + "." + ds[-1])
                return val
            # 3차: 2자리/1자리 정수
            if len(ds) in (1, 2):
                return float("".join(ds))
        return None

    value = run_ocr(thresh)

    # 7) 비현실적 값 간단 보정(산업 패널 상식선)
    if value is not None:
        if value >= 100:      # 759 같은 오인식 방지
            value = value / 10.0
        if value < -30 or value > 120:  # 말도 안 되는 범위 컷
            return None
    return value



# ----------------------------
# 2. LED 점등 여부 판단
# ----------------------------
def led_color_status(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    red_mask1 = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
    red_mask2 = cv2.inRange(hsv, (170, 100, 100), (180, 255, 255))
    red_mask = cv2.bitwise_or(red_mask1, red_mask2)
    green_mask = cv2.inRange(hsv, (40, 40, 80), (90, 255, 255))
    yellow_mask = cv2.inRange(hsv, (15, 100, 100), (40, 255, 255))

    masks = {"red": red_mask, "green": green_mask, "yellow": yellow_mask}
    color_ratios = {k: (mask > 0).mean() for k, mask in masks.items()}
    dominant_color = max(color_ratios, key=color_ratios.get)

    is_on = color_ratios[dominant_color] > 0.05
    return is_on, color_ratios


# ----------------------------
# 3. 이상 판단 함수
# ----------------------------
def detect_abnormal(temp, led_status):
    if led_status.get("overheat", {}).get("on", False):
        return "⚠️ 과열 경고"
    if not led_status.get("power", {}).get("on", True):
        return "⚠️ 전원 꺼짐"
    if temp is not None and temp > 60:
        return f"⚠️ 온도 이상 ({temp:.1f}°C)"
    return "정상 상태"


# ----------------------------
# 4. 시각화 함수 (OCR 실패 표시 포함)
# ----------------------------
def draw_detection_results(img, results, led_status, temp_value, abnormal_msg):
    annotated = img.copy()

    for b in results[0].boxes:
        cls = results[0].names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        color = (0, 255, 0)
        label = cls

        if cls == "temperature":
            if temp_value is None:
                label += ": OCR 실패"
                color = (0, 0, 255)
            else:
                label += f": {temp_value:.1f}°C"
                color = (255, 255, 0)
        else:
            if led_status.get(cls, {}).get("on", False):
                label += " (ON)"
                color = (0, 255, 0)
            else:
                label += " (OFF)"
                color = (0, 0, 255)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(annotated, label, (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)

    cv2.putText(annotated, abnormal_msg, (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                (0, 0, 255) if "⚠️" in abnormal_msg else (0, 255, 0), 3, cv2.LINE_AA)
    return annotated


# ----------------------------
# 5. 메인 로직
# ----------------------------
def main():
    module_model = YOLO(MODULE_MODEL_PATH)
    panel_model = YOLO(PANEL_MODEL_PATH)

    img = cv2.imread(IMAGE_PATH)
    if img is None:
        print("이미지 로드 실패:", IMAGE_PATH)
        return

    # ① AHU 전체 → 제어판 탐지
    module_results = module_model.predict(img, conf=0.2, device="cpu", verbose=False)
    panel_roi = None
    for box in module_results[0].boxes:
        cls_name = module_model.names[int(box.cls)]
        if "panel" in cls_name.lower():
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            panel_roi = img[y1:y2, x1:x2]
            break
    if panel_roi is None:
        print("제어판 탐지 실패")
        return

    # ② 제어판 내부 구성 탐지
    button_results = panel_model.predict(panel_roi, conf=0.5, device="cpu", verbose=False)
    led_status, temp_value = {}, None

    for b in button_results[0].boxes:
        cls = panel_model.names[int(b.cls)]
        print("탐지된 클래스:", cls)
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        roi = panel_roi[y1:y2, x1:x2]

        if cls == "temperature":
            temp_value = ocr_temperature(roi)
        else:
            is_on, color_info = led_color_status(roi)
            led_status[cls] = {"on": is_on, "color": color_info}

    # ③ 이상 탐지
    result_msg = detect_abnormal(temp_value, led_status)

    print(f"온도: {temp_value if temp_value is not None else '인식 실패'}°C")
    for k, v in led_status.items():
        print(f"{k}: {'ON' if v['on'] else 'OFF'}  (색상 비율: {v['color']})")
    print("결론:", result_msg)

    # ④ 시각화 및 저장
    annotated = draw_detection_results(panel_roi, button_results, led_status, temp_value, result_msg)
    cv2.imwrite("detected_panel_result4.jpg", annotated)
    print("결과 이미지 저장 완료: detected_panel_result4.jpg")


if __name__ == "__main__":
    main()
