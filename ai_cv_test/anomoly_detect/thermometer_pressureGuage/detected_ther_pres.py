import cv2
import numpy as np
import os
from ultralytics import YOLO
import math


# 1. 게이지 값 계산 (빠른 버전)
def detect_gauge_value_fast(
    img_path, 
    min_angle=230, 
    max_angle=320, 
    min_value=0, 
    max_value=2, 
    resize_limit=400
):
    img = cv2.imread(img_path)
    if img is None:
        print(f"이미지 로드 실패: {img_path}")
        return None, None

    h, w = img.shape[:2]

    # [1] 이미지 크기 조정 (속도 개선)
    scale = resize_limit / max(h, w) if max(h, w) > resize_limit else 1.0
    if scale < 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]

    # [2] 전처리
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # [3] 원 검출
    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, 1, 200,
        param1=100, param2=22,
        minRadius=50, maxRadius=0
    )

    img_center = np.array([w / 2, h / 2])
    if circles is None:
        x0, y0 = w // 2, h // 2
        R = min(h, w) // 2 - 40
    else:
        circles = np.uint16(np.around(circles))[0]
        x0, y0, R = max(
            circles,
            key=lambda c: (c[2] * 0.7) - np.linalg.norm(np.array([c[0], c[1]]) - img_center)
        )

    # [4] 엣지 검출 + 중심부 제거
    edges = cv2.Canny(blur, 50, 150)
    yy, xx = np.indices(edges.shape)
    rr = np.sqrt((xx - x0) ** 2 + (yy - y0) ** 2)

    mask_annulus = (rr > R * 0.2) & (rr < R * 0.9)
    mask_textband = (rr > R * 0.45) & (rr < R * 0.65)
    edges[~mask_annulus] = 0
    edges[mask_textband] = 0

    # [5] 각도 투표 (속도 개선)
    thetas = np.deg2rad(np.arange(0, 360, 2.0))
    scores = []
    for th in thetas:
        xs = (x0 + np.cos(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
        ys = (y0 - np.sin(th) * np.linspace(R * 0.25, R * 0.9, 60)).astype(int)
        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)
        scores.append(edges[ys, xs].sum())

    if len(scores) == 0:
        print("엣지 데이터 부족으로 탐지 불가")
        return None, None

    best_idx = int(np.argmax(scores))
    angle = (np.rad2deg(thetas[best_idx]) + 360) % 360

    # [6] 반전 보정
    opp_angle = (angle + 180) % 360
    xs1 = (x0 + np.cos(np.deg2rad(angle)) * np.linspace(R*0.3, R*0.9, 30)).astype(int)
    ys1 = (y0 - np.sin(np.deg2rad(angle)) * np.linspace(R*0.3, R*0.9, 30)).astype(int)
    xs2 = (x0 + np.cos(np.deg2rad(opp_angle)) * np.linspace(R*0.3, R*0.9, 30)).astype(int)
    ys2 = (y0 - np.sin(np.deg2rad(opp_angle)) * np.linspace(R*0.3, R*0.9, 30)).astype(int)
    score1 = edges[ys1, xs1].sum()
    score2 = edges[ys2, xs2].sum()
    if score2 > score1:
        angle = opp_angle

    # [7] 각도 → 측정값 변환
    def cw_delta(a, b): return (a - b) % 360
    sweep_cw = cw_delta(min_angle, max_angle)
    if sweep_cw == 0:
        sweep_cw = 360
    progressed = cw_delta(min_angle, angle)
    ratio = progressed / sweep_cw
    ratio = float(np.clip(ratio, 0, 1))
    value = min_value + ratio * (max_value - min_value)

    # [8] 시각화
    vis = img.copy()
    draw_angle = angle % 360
    x2 = int(x0 + np.cos(np.deg2rad(draw_angle)) * R * 0.85)
    y2 = int(y0 - np.sin(np.deg2rad(draw_angle)) * R * 0.85)
    cv2.circle(vis, (int(x0), int(y0)), 5, (0, 255, 0), -1)
    cv2.line(vis, (int(x0), int(y0)), (x2, y2), (0, 0, 255), 3)
    cv2.putText(vis, f"Value: {value:.2f}", (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

    out_path = os.path.splitext(img_path)[0] + "_fast_result.jpg"
    cv2.imwrite(out_path, vis)
    print(f"결과 저장: {out_path}")
    print(f"측정값: {value:.2f} / 각도: {angle:.2f}°")

    return angle, value



# 2. 이상 판단 로직
def judge_abnormal(sensor_type, value):
    if sensor_type == "thermometer":
        if value > 80:
            return "온도 과열 경고", "high"
        elif value < 5:
            return "온도 너무 낮음", "low"
        else:
            return "정상", "normal"
    elif sensor_type == "pressure_gauge":
        if value > 1.5:
            return "압력 과다", "high"
        elif value < 0.2:
            return "압력 부족", "low"
        else:
            return "정상", "normal"
    return "Unknown type", "unknown"


# 3. YOLO 탐지 → 게이지 분석 파이프라인
def analyze_module_gauges(image_path):
    model = YOLO("-AHU-module-detection-2/runs/train/module_yolo11n/weights/best.pt")
    results = model.predict(image_path, conf=0.5, device="cpu", verbose=False)
    img = cv2.imread(image_path)
    h, w = img.shape[:2]

    for box in results[0].boxes:
        cls = model.names[int(box.cls)]
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        crop = img[y1:y2, x1:x2]

        if cls in ["thermometer", "pressure_gauge"]:
            crop_path = f"crop_{cls}.jpg"
            cv2.imwrite(crop_path, crop)
            print(f"{cls} 영역 저장: {crop_path}")

            # 센서 종류별 파라미터
            if cls == "thermometer":
                angle, value = detect_gauge_value_fast(
                    crop_path,
                    min_angle=230, max_angle=320,
                    min_value=0, max_value=100
                )
                unit = "°C"
            else:
                angle, value = detect_gauge_value_fast(
                    crop_path,
                    min_angle=230, max_angle=320,
                    min_value=0, max_value=2
                )
                unit = "MPa"

            if angle is not None:
                msg, status = judge_abnormal(cls, value)
                print(f"{cls}: {value:.2f}{unit} → {msg}")
            else:
                print(f"{cls}: 지침 인식 실패")


# 4. 실행
if __name__ == "__main__":
    analyze_module_gauges("thermometer.jpeg")
