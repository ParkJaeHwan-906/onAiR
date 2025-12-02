import cv2
import numpy as np
import argparse
from gauge_anomaly import analyze_gauge
from fan_belt_anomaly import analyze_fan_belt
from panel_anomaly import analyze_panel
from ultralytics import YOLO
from loguru import logger



#---------------------
# Gauge needle & value overlay
# -----------------------------
def draw_gauge_overlay(frame, gauge_result, box):
    res = gauge_result.get("results", {})
    val = res.get("value")
    angle = res.get("angle")
    cx = res.get("cx")
    cy = res.get("cy")
    ex = res.get("ex")
    ey = res.get("ey")

    # value 표기
    if val is not None:
        txt = f"Value: {val:.2f}"
        cv2.putText(frame, txt, (box["x1"], box["y1"] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

    # 중심점
    if cx is not None and cy is not None:
        cv2.circle(frame, (int(cx), int(cy)), 5, (0, 255, 0), -1)

    # 바늘 라인
    if ex is not None and ey is not None and cx is not None and cy is not None:
        cv2.line(frame, (int(cx), int(cy)), (int(ex), int(ey)),
                 (0, 0, 255), 3)


# -----------------------------
# Neon box + label
# -----------------------------
def draw_neon_box(frame, box, label, color=(0,255,0)):
    x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]

    # glow 외곽
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1-2, y1-2), (x2+2, y2+2), color, 6)
    frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)

    # 메인 박스
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    # label
    cv2.putText(frame, label,
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                color, 2)
    return frame


# -----------------------------
# Combined overlay (YOLO + anomalies)
# -----------------------------
def render_final_overlay(frame, yolo_boxes, anomalies):
    # 기본 YOLO 박스 표시
    for b in yolo_boxes:
        label = f"{b['label']} ({b['confidence']:.2f})"
        frame = draw_neon_box(frame, b, label)

    # Gauge 전용 오버레이
    gauge = anomalies.get("gauge", {})
    gs = gauge.get("status", "not_found")
    gauge_boxes = [b for b in yolo_boxes if b["label"] in ("pressure_gauge", "thermometer", "temperature_FND")]

    if gauge_boxes and gs != "not_found":
        draw_gauge_overlay(frame, gauge, gauge_boxes[0])

        # 상태 표시
        if gs == "normal":
            txt = "Gauge: NORMAL"
            color = (0, 255, 0)
        elif gs == "anomaly":
            txt = "Gauge: ABNORMAL"
            color = (0, 0, 255)
        else:
            txt = "Gauge: NO DETECTION"
            color = (0, 165, 255)

        cv2.putText(frame, txt, (30, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)

    # Fan/Belt 상태 표시
    fan = anomalies.get("fan_belt", {})
    fs = fan.get("status", "not_found")

    if fs == "normal":
        cv2.putText(frame, "Fan/Belt: NORMAL", (30, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    elif fs == "anomaly":
        cv2.putText(frame, "Fan/Belt: ABNORMAL", (30, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    # Panel 상태 표시
    panel = anomalies.get("panel", {})
    ps = panel.get("status", "not_found")

    if ps == "normal":
        cv2.putText(frame, "Panel: NORMAL", (30, 160),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    elif ps == "anomaly":
        cv2.putText(frame, "Panel: ABNORMAL", (30, 160),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    return frame
    
def run_yolo(model, frame):
    results = model(frame)
    detections = []

    for r in results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf < 0.70:
                continue
            cls = int(box.cls[0])
            label = model.names[cls]
            xyxy = box.xyxy[0].cpu().numpy().astype(int)
            detections.append({
                "label": label,
                "confidence": conf,
                "x1": xyxy[0], "y1": xyxy[1],
                "x2": xyxy[2], "y2": xyxy[3],
            })
    return detections

async def run_anomaly(frame, boxes):
    result = {
        "fan_belt": {"status": "not_found", "results": {}, "message": ""},
        "gauge": {"status": "not_found", "results": {}, "message": ""},
        "panel": {"status": "not_found", "results": {}, "message": ""},
        "has_anomaly": False
    }

    belts = [b for b in boxes if b["label"] == "belt"]
    gauges = [b for b in boxes if b["label"] in ("pressure_gauge", "thermometer", "temperature_FND")]
    panels = [b for b in boxes if b["label"] in ("control_panel", "AHU_pannel")]
    parts = [b for b in boxes if b["label"] not in ("control_panel", "AHU_pannel")]

    if belts:
        frames = [frame for _ in range(8)]  # static image → fake 8 frames
        fan = await analyze_fan_belt(frames, belts)
        result["fan_belt"] = fan
        if fan.get("status") != "normal":
            result["has_anomaly"] = True

    if gauges:
        gauge = await analyze_gauge(frame, gauges)
        result["gauge"] = gauge
        if gauge.get("status") != "normal":
            result["has_anomaly"] = True

    if panels:
        panel = await analyze_panel(frame, panels, parts)
        result["panel"] = panel
        if panel.get("status") != "normal":
            result["has_anomaly"] = True

    return result
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", default="result.jpg")
    args = parser.parse_args()

    import asyncio

    logger.info(f"Loading YOLO model: {args.model}")
    model = YOLO(args.model)

    frame = cv2.imread(args.image)
    if frame is None:
        raise ValueError("Image load failed")

    yolo_boxes = run_yolo(model, frame)
    anomalies = asyncio.run(run_anomaly(frame, yolo_boxes))

    if anomalies["has_anomaly"]:
        cv2.putText(frame, "ANOMALY DETECTED", (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
    else:
        cv2.putText(frame, "NORMAL", (30, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 3)

    frame = render_final_overlay(frame, yolo_boxes, anomalies)

    cv2.imwrite(args.output, frame)
    logger.info(f"Saved → {args.output}")

