import cv2
from ultralytics import YOLO

VIDEO_PATH = "./video.mp4"
MODEL1_PATH = "./runs/detect/train/weights/best.pt"

CONF_THRESH = 0.8

def filter_conf(results, thresh):
    """Results 객체 내부의 boxes를 confidence 기준으로 필터링"""
    boxes = results.boxes
    mask = boxes.conf >= thresh
    boxes.data = boxes.data[mask]   # <-- 핵심: Results 객체의 boxes.data 직접 수정
    return results

def run_video_inference():
    model1 = YOLO(MODEL1_PATH)

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("비디오 열기 실패")
        return

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out = cv2.VideoWriter("new_yolo_model_2.mp4", fourcc, fps, (w, h))

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)
        time_sec = current_frame / fps

        # ------------------------------
        # 1) MODEL1
        # ------------------------------
        r1 = model1(frame, device=1, verbose=False)[0]
        r1 = filter_conf(r1, CONF_THRESH)

        annotated = r1.plot()
        out.write(annotated)

    cap.release()
    out.release()

if __name__ == "__main__":
    run_video_inference()
