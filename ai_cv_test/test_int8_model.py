import onnxruntime as ort
import cv2
import numpy as np

# ===========================
# 0. Class Names
# ===========================
CLASS_NAMES = [
    "AHU", "AHU_pannel", "Boiler", "Chiler", "belt",
    "button_off", "button_on", "control_panel", "overheat_light",
    "power_light", "pressure_gauge", "run_light",
    "temperature_FND", "thermometer"
]

# ===========================
# 1. Letterbox (YOLO 공식 preprocessing)
# ===========================
def letterbox(im, new_shape=768, color=(114, 114, 114)):
    shape = im.shape[:2]  # (h, w)

    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))

    dw = new_shape[1] - new_unpad[0]
    dh = new_shape[0] - new_unpad[1]

    dw /= 2
    dh /= 2

    im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    im = cv2.copyMakeBorder(im, int(dh), int(dh), int(dw), int(dw),
                            cv2.BORDER_CONSTANT, value=color)

    return im, r, dw, dh

# ===========================
# 2. Preprocess
# ===========================
def preprocess(frame, size=768):
    img, r, dw, dh = letterbox(frame, size)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_rgb = img_rgb.astype(np.float32) / 255.0
    img_chw = np.transpose(img_rgb, (2, 0, 1))
    return np.expand_dims(img_chw, 0), r, dw, dh

# ===========================
# 3. Postprocess
# ===========================
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def compute_iou(box, boxes):
    x1, y1, x2, y2 = box
    xx1 = np.maximum(x1, boxes[:, 0])
    yy1 = np.maximum(y1, boxes[:, 1])
    xx2 = np.minimum(x2, boxes[:, 2])
    yy2 = np.minimum(y2, boxes[:, 3])
    inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
    area1 = (x2 - x1) * (y2 - y1)
    area2 = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / (area1 + area2 - inter + 1e-6)

def nms(boxes, scores, iou_thresh=0.5):
    idxs = scores.argsort()[::-1]
    keep = []
    while len(idxs) > 0:
        current = idxs[0]
        keep.append(current)
        if len(idxs) == 1:
            break
        ious = compute_iou(boxes[current], boxes[idxs[1:]])
        idxs = idxs[1:][ious < iou_thresh]
    return keep

def postprocess(outputs, r, dw, dh, orig_w, orig_h, conf_thres=0.45, iou_thres=0.5):
    preds = outputs[0][0]  # (N, 18)

    cx = preds[:, 0]
    cy = preds[:, 1]
    w  = preds[:, 2]
    h  = preds[:, 3]
    conf = sigmoid(preds[:, 4])
    cls_logits = sigmoid(preds[:, 5:])

    cls_scores = cls_logits.max(axis=1)
    cls_ids = cls_logits.argmax(axis=1)

    scores = conf * cls_scores
    
    mask = scores > conf_thres
    cx, cy, w, h, scores, cls_ids = (
        cx[mask], cy[mask], w[mask], h[mask], scores[mask], cls_ids[mask]
    )

    x1 = cx - w / 2
    y1 = cy - h / 2
    x2 = cx + w / 2
    y2 = cy + h / 2

    # Remove padding & scale back
    x1 = (x1 - dw) / r
    y1 = (y1 - dh) / r
    x2 = (x2 - dw) / r
    y2 = (y2 - dh) / r

    boxes = np.stack([x1, y1, x2, y2], axis=1)
    keep = nms(boxes, scores, iou_thresh=iou_thres)

    return boxes[keep], scores[keep], cls_ids[keep]

# ===========================
# 4. Inference + Visualization
# ===========================
def visualize_onnx(input_path, output_path="result.jpg", size=768):
    # Load ONNX model
    session = ort.InferenceSession(
        "runs/detect/train/weights/best.onnx",
        providers=["CPUExecutionProvider"]
    )
    input_name = session.get_inputs()[0].name

    # Load image
    frame = cv2.imread(input_path)
    orig_h, orig_w = frame.shape[:2]

    # preprocess
    input_tensor, r, dw, dh = preprocess(frame, size)

    # inference
    outputs = session.run(None, {input_name: input_tensor})

    # postprocess
    boxes, scores, class_ids = postprocess(outputs, r, dw, dh, orig_w, orig_h)

    # draw boxes
    for box, score, cls in zip(boxes, scores, class_ids):
        x1, y1, x2, y2 = box.astype(int)
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(orig_w - 1, x2); y2 = min(orig_h - 1, y2)

        label = f"{CLASS_NAMES[cls]} {score:.2f}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imwrite(output_path, frame)
    print(f"saved: {output_path}")

# ===========================
# RUN TEST
# ===========================
visualize_onnx("control_panel2.jpeg", "onnx_result.jpg", size=768)
