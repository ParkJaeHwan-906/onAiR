import numpy as np

# === 카메라 내부 파라미터 (Intrinsic Matrix) ===
# fx, fy : 초점 거리 (픽셀 단위)
# cx, cy : 이미지 중심 (Principal Point)
# 일반적인 USB 카메라나 라즈베리파이 카메라 기준 대략적인 값

fx = 520.0   # 가로 방향 focal length
fy = 520.0   # 세로 방향 focal length
cx = 320.0   # 영상 중심 x (640 / 2)
cy = 240.0   # 영상 중심 y (480 / 2)

K = np.array([
    [fx, 0, cx],
    [0, fy, cy],
    [0,  0,  1]
], dtype=np.float64)

# 저장
np.save("../data/camera_intrinsics.npy", K)
print("Saved intrinsic matrix:\n", K)
