def overlay_status(frame, yolo_list, anomalies):
    y = 30
    dy = 25

    # ---- YOLO text ----
    yolo_text = "[YOLO] " + ", ".join(
        [f"{d['label']}({d['confidence']:.2f})" for d in yolo_list]
    )
    cv2.putText(frame, yolo_text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (0, 255, 255), 2)
    y += dy

    # ---- Fan/Belt ----
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

    # ---- Gauge ----
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

    # ---- ★★ Gauge Needle Overlay ★★ ----
    gauge_results = gauge.get("results", {})

    for box in yolo_list:
        lbl = box["label"]
        if lbl not in ("pressure_gauge", "thermometer", "temperature_FND"):
            continue

        if lbl not in gauge_results:
            continue

        angle = gauge_results[lbl].get("angle")
        if angle is None:
            continue

        x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)
        R = int(min((x2 - x1), (y2 - y1)) * 0.45)

        rad = np.deg2rad(angle)
        x_end = int(cx + np.cos(rad) * R)
        y_end = int(cy - np.sin(rad) * R)

        cv2.line(frame, (cx, cy), (x_end, y_end), (0, 0, 255), 3)
        cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)

    # ---- Panel ----
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
