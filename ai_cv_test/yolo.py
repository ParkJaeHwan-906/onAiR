import cv2
from ultralytics import YOLO
def draw_detection_results(img, results, led_status, temp_value, abnormal_msg):
    annotated = img.copy()

    # YOLO 박스 그리기
    for b in results[0].boxes:
        cls = results[0].names[int(b.cls)]
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        color = (0, 255, 0)  # 박스 색
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated,
            cls,
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

    return annotated

model = YOLO("final_v1.pt")

img = cv2.imread("KakaoTalk_Photo_2025-11-23-19-13-55.jpeg")
results = model(img)

annotated = draw_detection_results(
    img,
    results,
    led_status=None,
    temp_value=None,
    abnormal_msg=None
)

cv2.imwrite("yolo_result.jpg", annotated)