import cv2
from ultralytics import YOLO

BOX_COLORS = {
    "temperature_FND": (0, 128, 255),
    "power_light":   (0, 0, 255),
    "run_light":     (0, 255, 0),
    "overheat_light": (0, 255, 255),
    "button_on":  (255, 128, 0),
    "button_off": (150, 50, 200),
    "default": (0, 255, 0),
    "control_panel" : (0, 255, 255)
}

def glow_rect(annotated, x1, y1, x2, y2, color):
    overlay = annotated.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, 0.25, annotated, 0.75, 0, annotated)
    return annotated

def analyze_led_hsv(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    mean_h = float(h.mean())
    mean_s = float(s.mean())
    mean_v = float(v.mean())

    bright_mask = (v > 180) & (s > 80)
    bright_ratio = float(bright_mask.mean())

    return {
        "mean_h": mean_h,
        "mean_s": mean_s,
        "mean_v": mean_v,
        "bright_ratio": bright_ratio
    }
    
def draw_detection_results(img, results, led_status, temp_value, abnormal_msg):
    annotated = img.copy()

    power_on = False
    run_on = False
    overheat_on = False

    for b in results[0].boxes:
        cls = results[0].names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        color = BOX_COLORS.get(cls, BOX_COLORS["default"])
        label_text = cls

        # ROI 추출
        roi = img[y1:y2, x1:x2]
        if roi is None or roi.size == 0:
            continue

        # HSV 분석
        hsv_info = analyze_led_hsv(roi)

        # 콘솔 출력
        print(f"[{cls}] HSV = {hsv_info}")

        # ===========================
        # LED 상태 판별 (임시: HSV 기반)
        # ===========================
        is_on = hsv_info["bright_ratio"] > 0.12

        if cls == "power_light":
            power_on = is_on
        elif cls == "run_light":
            run_on = is_on
        elif cls == "overheat_light":
            overheat_on = is_on


        # ===========================
        # Glow & 네온 효과 (ON LED)
        # ===========================
        if cls in ["power", "run", "overheat"]:
            if cls == "power" and power_on:
                annotated = glow_rect(annotated, x1, y1, x2, y2, (0,0,255))
                cv2.rectangle(annotated, (x1-3, y1-3), (x2+3, y2+3), (0,0,255), 5)
                label_text = f"{cls} ON"

            elif cls == "run" and run_on:
                annotated = glow_rect(annotated, x1, y1, x2, y2, (0,255,0))
                cv2.rectangle(annotated, (x1-3, y1-3), (x2+3, y2+3), (0,255,0), 5)
                label_text = f"{cls} ON"

            elif cls == "overheat" and overheat_on:
                annotated = glow_rect(annotated, x1, y1, x2, y2, (0,255,255))
                cv2.rectangle(annotated, (x1-3, y1-3), (x2+3, y2+3), (0,255,255), 5)
                label_text = f"{cls} ON"

            else:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)  # OFF LED 얇은 박스
                label_text = f"{cls} OFF"

        else:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # 라벨
        cv2.putText(
            annotated,
            label_text,
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            color,
            3
        )

    # ===========================
    # 상단 상태 텍스트 요약
    # ===========================
    status_text = f"POWER: {'ON' if power_on else 'OFF'} | RUN: {'ON' if run_on else 'OFF'} | OVERHEAT: {'ON' if overheat_on else 'OFF'}"

    cv2.putText(
        annotated,
        status_text,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        3
    )

    return annotated


# ================================
# YOLO 실행
# ================================

model = YOLO("all.pt")

img = cv2.imread("origin/control_panel.jpeg")
results = model(img)

annotated = draw_detection_results(
    img,
    results,
    led_status=None,
    temp_value=None,
    abnormal_msg=None
)

cv2.imwrite("output.jpg", annotated)
