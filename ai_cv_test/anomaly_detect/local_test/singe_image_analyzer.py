import cv2
import argparse
from ultralytics import YOLO
from loguru import logger

from gauge_anomaly import analyze_gauge
from fan_belt_anomaly import analyze_fan_belt
from panel_anomaly import analyze_panel


def fmt(v):
    return "N/A" if v is None else f"{v:.2f}"


def overlay_status(frame, yolo_list, anomalies):
    y = 30
    dy = 25

    yolo_text = "[YOLO] " + ", ".join(
        [f"{d['label']}({d['confidence']:.2f})" for d in yolo_list]
    )
    cv2.putText(frame, yolo_text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (0, 255, 255), 2)
    y += dy

    fan = anomalies.get("fan_belt", {})
    fs = fan.get("status", "not_found")
    amp = fan.get("results", {}).get("mean_mag")
    delta = fan.get("results", {}).get("motion_delta")

    if fs == "anomaly":
        txt = f"[Fan/Belt] Abnormal | amp={fmt(amp)} delta={fmt(delta)}"
        color = (0, 0, 255)
    elif fs == "normal":
        txt = f"[Fan/Belt] Normal | amp={fmt(amp)} delta={fmt(delta)}"
        color = (0, 255, 0)
    else:
        txt = "[Fan/Belt] Not detected"
        color = (200, 200, 200)

    cv2.putText(frame, txt, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    y += dy

    gauge = anomalies.get("gauge", {})
    gs = gauge.get("status", "not_found")
    gv = gauge.get("results", {}).get("value")
    ga = gauge.get("results", {}).get("angle")

    if gs == "anomaly":
        txt = f"[Gauge] Abnormal | val={fmt(gv)} angle={fmt(ga)}°"
        color = (0, 0, 255)
    elif gs == "normal":
        txt = f"[Gauge] Normal | val={fmt(gv)} angle={fmt(ga)}°"
        color = (0, 255, 0)
    elif gs == "no_detection":
        txt = "[Gauge] No detection | val=N/A angle=N/A"
        color = (0, 165, 255)
    else:
        txt = "[Gauge] Not detected"
        color = (200, 200, 200)

    cv2.putText(frame, txt, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    y += dy

    panel = anomalies.get("panel", {})
    ps = panel.get("status", "not_found")
    led = panel.get("results", {}).get("led_color")
    temp = panel.get("results", {}).get("temperature")

    if ps == "anomaly":
        txt = f"[Panel] Abnormal | LED={led or 'N/A'} temp={temp or 'N/A'}"
        color = (0, 0, 255)
    elif ps == "normal":
        txt = f"[Panel] Normal | LED={led or 'N/A'} temp={temp or 'N/A'}"
        color = (0, 255, 0)
    else:
        txt = "[Panel] Not detected"
        color = (200, 200, 200)

    cv2.putText(frame, txt, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
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


def draw_bbox(frame, box, color):
    cv2.rectangle(frame, (box["x1"], box["y1"]),
                  (box["x2"], box["y2"]), color, 2)


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

    for b in yolo_boxes:
        draw_bbox(frame, b, (0, 255, 0))

    if anomalies["has_anomaly"]:
        cv2.putText(frame, "ANOMALY DETECTED", (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
    else:
        cv2.putText(frame, "NORMAL", (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 3)

    frame = overlay_status(frame, yolo_boxes, anomalies)

    cv2.imwrite(args.output, frame)
    logger.info(f"Saved → {args.output}")
