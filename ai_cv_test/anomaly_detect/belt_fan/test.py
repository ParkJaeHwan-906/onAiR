import cv2, numpy as np, matplotlib.pyplot as plt

cap = cv2.VideoCapture("fan_spin.mp4")
x, y, w, h = 245, 62, 245, 325
prev_gray = None

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ 영상 끝 or 로드 실패")
        break

    frame = cv2.resize(frame, (640, 480))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    roi_gray = gray[y:y+h, x:x+w]
    if roi_gray.size == 0:
        print("⚠️ ROI 영역이 비어있음. 좌표 다시 확인 필요.")
        break

    if prev_gray is not None:
        roi_prev = prev_gray[y:y+h, x:x+w]
        flow = cv2.calcOpticalFlowFarneback(roi_prev, roi_gray, None,
                                            0.5, 3, 15, 3, 5, 1.2, 0)
        mag, ang = cv2.cartToPolar(flow[...,0], flow[...,1])
        flow_mean = np.mean(mag)
        print(f"Flow mean: {flow_mean:.4f}")

        plt.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        plt.title(f"Flow mean: {flow_mean:.4f}")
        plt.axis('off')
        plt.show()
    else:
        print("초기 프레임 저장 중...")

    prev_gray = gray.copy()
