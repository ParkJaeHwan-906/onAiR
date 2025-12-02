import cv2
import numpy as np
import math

def generate_motion_video(name, mode, fps=30, duration=5, size=(480,480)):
    w, h = size
    center = (w//2, h//2)
    total_frames = fps * duration

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(f"{name}.mp4", fourcc, fps, size)

    angle = 0
    for i in range(total_frames):
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        # ---- 속도 제어 ----
        if mode == "normal":
            speed = 5
        elif mode == "accelerate":
            speed = 2 + 8 * (i / total_frames)
        elif mode == "decelerate":
            speed = 10 - 8 * (i / total_frames)
        elif mode == "irregular":
            # 복수 주기 + 진폭 확대 → 느려졌다 빨라졌다 반복
            speed = 5 + 4 * math.sin(i / 2.0) + 2 * math.sin(i / 7.0)
        else:
            speed = 5

        angle += speed

        # ---- 좌표 계산 ----
        x1 = int(center[0] + 150 * math.cos(math.radians(angle)))
        y1 = int(center[1] + 150 * math.sin(math.radians(angle)))
        x2 = int(center[0] - 150 * math.cos(math.radians(angle)))
        y2 = int(center[1] - 150 * math.sin(math.radians(angle)))

        # 중심 흔들림 추가 (약간만)
        cx, cy = center
        if mode == "irregular":
            cx += int(10 * math.sin(i / 3.0))
            cy += int(10 * math.cos(i / 4.0))

        # ---- 그리기 ----
        cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 255), 10)
        cv2.circle(frame, (cx, cy), 10, (255, 255, 255), -1)

        out.write(frame)

    out.release()
    print(f"{name}.mp4 저장 완료")


# ---- 영상 4종 생성 ----
generate_motion_video("normal_motion", "normal")
generate_motion_video("irregular_vibration", "irregular")
generate_motion_video("accelerate_motion", "accelerate")
generate_motion_video("decelerate_motion", "decelerate")
