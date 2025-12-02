import onnxruntime as ort
import numpy as np
import cv2

session = ort.InferenceSession(
    "runs/detect/train2/weights/best.onnx",
    providers=["CPUExecutionProvider"]
)
input_name = session.get_inputs()[0].name

frame = cv2.imread("control_panel2.jpeg")

def letterbox(img, new_shape=768, color=(114,114,114)):
    h, w = img.shape[:2]
    scale = min(new_shape/h, new_shape/w)
    nh, nw = int(h*scale), int(w*scale)
    
    resized = cv2.resize(img, (nw, nh))
    top = (new_shape-nh)//2
    bottom = new_shape-nh-top
    left = (new_shape-nw)//2
    right = new_shape-nw-left
    padded = cv2.copyMakeBorder(resized, top, bottom, left, right,
                                cv2.BORDER_CONSTANT, value=color)
    return padded, scale, left, top

resized, scale, pad_x, pad_y = letterbox(frame, 768)

img = resized[:, :, ::-1].transpose(2,0,1)
img = img.astype(np.float32) / 255.0
img = np.expand_dims(img, 0)

outputs = session.run(None, {input_name: img})

pred = outputs[0][0]    # (18,12096)

print("\n=== RAW PRED SAMPLE ===")
print(pred[:, 0:10])
