import cv2
import os
from ultralytics import YOLO

RESIZE = (480, 360)
CONF_THRESH = 0.15
RESULT_DIR = "yolo_detect_results"


def yolo_detect_video(video_path, model_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"영상 열기 실패: {video_path}")
        return

    os.makedirs(RESULT_DIR, exist_ok=True)
    fname = os.path.basename(video_path)
    result_path = os.path.join(RESULT_DIR, f"yolo_detect_{fname}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30

    out = cv2.VideoWriter(
        result_path,
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps,
        RESIZE
    )

    model = YOLO(model_path)
    frame_idx = 0

    print(f"\nYOLO 탐지 시작: {fname}")
    print(f"--- CONF_THRESH = {CONF_THRESH} ---\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, RESIZE)
        frame_idx += 1

        # 탐지 시도 로그
        print(f"[Frame {frame_idx}] 탐지 시도 중...")

        # YOLO 추론
        results = model.predict(frame, conf=CONF_THRESH, verbose=False)
        detections = results[0].boxes

        # 탐지 결과 없는 경우
        if len(detections) == 0:
            print(f"  → 탐지 없음")
        else:
            print(f"  → {len(detections)}개 탐지됨")

        # 박스 그리기
        for box in detections:
            cls_id = int(box.cls)
            cls_name = model.names[cls_id]
            conf = float(box.conf)

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(
                frame,
                f"{cls_name}:{conf:.2f}",
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2
            )

        # 결과 프레임 기록
        out.write(frame)

    cap.release()
    out.release()

    print(f"\nYOLO 탐지 영상 저장 완료 → {result_path}")


if __name__ == "__main__":
    video_path = "fan/normal_13fps.mp4"
    yolo_model = "final_v2.pt"
    yolo_detect_video(video_path, yolo_model)
