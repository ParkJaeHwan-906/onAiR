import cv2
import numpy as np
import onnxruntime as ort


# ========================
# Letterbox (Ultralytics 동일)
# ========================
def letterbox(img, new_shape=768, color=(114, 114, 114)):
    h, w = img.shape[:2]
    scale = min(new_shape / h, new_shape / w)
    nh, nw = int(h * scale), int(w * scale)

    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)

    top = (new_shape - nh) // 2
    bottom = new_shape - nh - top
    left = (new_shape - nw) // 2
    right = new_shape - nw - left

    padded = cv2.copyMakeBorder(resized, top, bottom, left, right,
                                cv2.BORDER_CONSTANT, value=color)

    return padded, scale, left, top


# ========================
# YOLO11 ONNX Postprocess
# ========================
def postprocess_yolo11(outputs, scale, pad_x, pad_y,
                       orig_w, orig_h, conf_thres=0.45):
    pred = outputs[0]  # (1, 18, 12096)
    pred = pred[0].T   # → (12096, 18)

    # 분리
    xyxy = pred[:, 0:4]
    obj_conf = pred[:, 4]
    cls_conf = pred[:, 5:]

    # 스코어 계산
    cls_ids = cls_conf.argmax(1)
    cls_scores = cls_conf.max(1)
    scores = obj_conf * cls_scores

    keep = scores > conf_thres
    if not keep.any():
        return [], [], []

    xyxy = xyxy[keep]
    scores = scores[keep]
    cls_ids = cls_ids[keep]

    # Letterbox 복원
    xyxy[:, 0] = (xyxy[:, 0] - pad_x) / scale
    xyxy[:, 1] = (xyxy[:, 1] - pad_y) / scale
    xyxy[:, 2] = (xyxy[:, 2] - pad_x) / scale
    xyxy[:, 3] = (xyxy[:, 3] - pad_y) / scale

    # 이미지 크기 클리핑
    xyxy[:, [0, 2]] = xyxy[:, [0, 2]].clip(0, orig_w)
    xyxy[:, [1, 3]] = xyxy[:, [1, 3]].clip(0, orig_h)

    return xyxy, scores, cls_ids


# ========================
# 박스 그리기
# ========================
def draw_boxes(frame, boxes, scores, cls_ids):
    for (x1, y1, x2, y2), sc, cid in zip(boxes, scores, cls_ids):
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        cv2.rectangle(frame, (x1, y1), (x2, y2),
                      (0, 255, 0), 2)
        cv2.putText(frame, f"{cid}:{sc:.2f}", (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 2)
    return frame


# ========================
# 비디오 → ONNX → 결과 저장
# ========================
def run_video_onnx(video_path, model_path, output_path="onnx_result.mp4"):
    session = ort.InferenceSession(
        model_path,
        providers=["CPUExecutionProvider"]
    )

    input_name = session.get_inputs()[0].name
    img_size = 768

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("비디오 열기 실패")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps, (orig_w, orig_h)
    )

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 1) letterbox
        inp, scale, pad_x, pad_y = letterbox(frame, img_size)

        # 2) RGB, CHW, normalize
        img = inp[:, :, ::-1].transpose(2, 0, 1)
        img = img.astype(np.float32) / 255.0
        img = np.expand_dims(img, 0)

        # 3) ONNX inference
        outputs = session.run(None, {input_name: img})

        # 4) decode
        boxes, scores, cls_ids = postprocess_yolo11(
            outputs, scale, pad_x, pad_y, orig_w, orig_h
        )

        # 5) draw
        annotated = draw_boxes(frame.copy(), boxes, scores, cls_ids)

        out.write(annotated)

    cap.release()
    out.release()
    print(f"Saved ONNX video → {output_path}")


if __name__ == "__main__":
    run_video_onnx(
        video_path="module.mp4",
        model_path="runs/detect/train/weights/best.onnx",
        output_path="onnnx_result.mp4"
    )
