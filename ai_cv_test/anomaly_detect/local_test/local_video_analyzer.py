import cv2
import numpy as np
import argparse
from ultralytics import YOLO
from loguru import logger

# --- IMPORT ANALYZER MODULES ---
from gauge_anomaly import analyze_gauge
from fan_belt_anomaly import analyze_fan_belt
from panel_anomaly import analyze_panel


def overlay_status(frame, yolo_list, anomalies):
    # 안전한 포맷팅
    def fmt(v):
        return "N/A" if v is None else f"{v:.2f}"

    y = 30
    dy = 25

    # -------------------------------
    # YOLO SUMMARY
    # -------------------------------
    yolo_text = "[YOLO] " + ", ".join(
        [f"{d['label']}({d['confidence']:.2f})" for d in yolo_list]
    )
    cv2.putText(frame, yolo_text, (20, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    y += dy

    # -------------------------------
    # FAN/BELT
    # -------------------------------
    fan = anomalies.get("fan_belt", {}) or {}
    fan_status = fan.get("status", "not_found")

    amp = fan.get("results", {}).get("mean_mag")
    delta = fan.get("results", {}).get("motion_delta")

    if fan_status == "anomaly":
        txt = f"[Fan/Belt] Abnormal | amp={fmt(amp)} delta={fmt(delta)}"
        color = (0, 0, 255)
    elif fan_status == "normal":
        txt = f"[Fan/Belt] Normal | amp={fmt(amp)} delta={fmt(delta)}"
        color = (0, 255, 0)
    else:
        txt = "[Fan/Belt] Not detected"
        color = (200, 200, 200)

    cv2.putText(frame, txt, (20, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    y += dy

    # -------------------------------
    # GAUGE
    # -------------------------------
    gauge = anomalies.get("gauge", {}) or {}
    gauge_status = gauge.get("status", "not_found")

    gauge_value = gauge.get("results", {}).get("value")
    gauge_angle = gauge.get("results", {}).get("angle")

    if gauge_status == "anomaly":
        txt = f"[Gauge] Abnormal | val={fmt(gauge_value)} angle={fmt(gauge_angle)}°"
        color = (0, 0, 255)
    elif gauge_status == "normal":
        txt = f"[Gauge] Normal | val={fmt(gauge_value)} angle={fmt(gauge_angle)}°"
        color = (0, 255, 0)
    else:
        txt = "[Gauge] Not detected"
        color = (200, 200, 200)

    cv2.putText(frame, txt, (20, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    y += dy

    # -------------------------------
    # PANEL
    # -------------------------------
    panel = anomalies.get("panel", {}) or {}
    panel_status = panel.get("status", "not_found")

    led_color = panel.get("results", {}).get("led_color")
    temp = panel.get("results", {}).get("temperature")

    txt_temp = temp if temp is not None else "N/A"
    txt_led = led_color if led_color is not None else "N/A"

    if panel_status == "anomaly":
        txt = f"[Panel] Abnormal | LED={txt_led} temp={txt_temp}"
        color = (0, 0, 255)
    elif panel_status == "normal":
        txt = f"[Panel] Normal | LED={txt_led} temp={txt_temp}"
        color = (0, 255, 0)
    else:
        txt = "[Panel] Not detected"
        color = (200, 200, 200)

    cv2.putText(frame, txt, (20, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    return frame




# ------------------------------
# YOLO inference
# ------------------------------
def run_yolo(model, frame):
    results = model(frame)
    detections = []

    for r in results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf < 0.70:
                continue
                
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].cpu().numpy().astype(int)

            detections.append({
                "label": label,
                "confidence": conf,
                "x1": xyxy[0],
                "y1": xyxy[1],
                "x2": xyxy[2],
                "y2": xyxy[3],
            })

    return detections


# ------------------------------
# Anomaly pipeline
# ------------------------------
async def run_anomaly(frame, yolo_boxes):
    result = {
        "fan_belt": {
            "status": "not_found",
            "message": "belt not detected",
            "results": {}
        },
        "gauge": {
            "status": "not_found",
            "message": "gauge not detected",
            "results": {}
        },
        "panel": {
            "status": "not_found",
            "message": "panel not detected",
            "results": {}
        },
        "has_anomaly": False,
        "description": []
    }

    # grouping
    belt_boxes = [b for b in yolo_boxes if b["label"] == "belt"]
    gauge_boxes = [b for b in yolo_boxes
                   if b["label"] in ("pressure_gauge", "thermometer", "temperature_FND")]
    panel_boxes = [b for b in yolo_boxes
                   if b["label"] in ("control_panel", "AHU_pannel")]
    part_boxes = [b for b in yolo_boxes
                  if b["label"] not in ("control_panel", "AHU_pannel")]

    # Fan/Belt
    if belt_boxes:
        frames = [frame for _ in range(8)]
        fan_res = await analyze_fan_belt(frames, belt_boxes)
        result["fan_belt"] = fan_res

        if fan_res.get("status") != "normal":
            result["has_anomaly"] = True
            result["description"].append(f"[Fan/Belt] {fan_res.get('message','')}")

    # Gauge
    if gauge_boxes:
        gauge_res = await analyze_gauge(frame, gauge_boxes)
        result["gauge"] = gauge_res

        if gauge_res.get("status") != "normal":
            result["has_anomaly"] = True
            result["description"].append(f"[Gauge] {gauge_res.get('message','')}")

    # Panel
    if panel_boxes:
        panel_res = await analyze_panel(frame, panel_boxes, part_boxes)
        result["panel"] = panel_res

        if panel_res.get("status") != "normal":
            result["has_anomaly"] = True
            result["description"].append(f"[Panel] {panel_res.get('message','')}")

    return result


# ------------------------------
# Overlay helpers
# ------------------------------
def draw_bbox(frame, box, color):
    cv2.rectangle(frame,
                  (box["x1"], box["y1"]),
                  (box["x2"], box["y2"]),
                  color, 2)


def draw_text(frame, text, x, y, color):
    cv2.putText(frame, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)


# ------------------------------
# MAIN
# ------------------------------
async def process_video(video_path, model_path, output_path):

    logger.info(f"Loading YOLO model: {model_path}")
    model = YOLO(model_path)

    cap = cv2.VideoCapture(video_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h)
    )

    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1

        # YOLO
        yolo_detections = run_yolo(model, frame)

        # anomaly
        anomaly_results = await run_anomaly(frame, yolo_detections)

        # draw YOLO boxes
        for b in yolo_detections:
            draw_bbox(frame, b, (0, 255, 0))

        # draw anomaly status banner
        if anomaly_results["has_anomaly"]:
            draw_text(frame, "ANOMALY DETECTED", 30, 40, (0, 0, 255))
        else:
            draw_text(frame, "NORMAL", 30, 40, (0, 255, 0))

        # overlay full HUD
        frame = overlay_status(frame, yolo_detections, anomaly_results)

        writer.write(frame)

        if frame_idx % 10 == 0:
            logger.info(f"Processed frame {frame_idx}")

    cap.release()
    writer.release()
    logger.info(f"Saved → {output_path}")


# ------------------------------
# ENTRY
# ------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, required=True)
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--output", type=str, default="output.mp4")

    args = parser.parse_args()

    import asyncio
    asyncio.run(process_video(args.video, args.model, args.output))
