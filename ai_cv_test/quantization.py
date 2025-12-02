from onnxruntime.quantization import quantize_dynamic, QuantType

model_fp32 = "runs/detect/train/weights/best.onnx"
model_int8 = "runs/detect/train/weights/best_int8.onnx"

quantize_dynamic(
    model_input=model_fp32,
    model_output=model_int8,
    weight_type=QuantType.QInt8   # 또는 QuantType.QUInt8
)

print("INT8 양자화 완료:", model_int8)