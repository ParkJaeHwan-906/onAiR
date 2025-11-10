import numpy as np

# 예: camera_matrix.npy, dist_coeffs.npy
camera_matrix = np.load("camera_intrinsics.npy")
dist_coeffs = np.load("dist_coeffs.npy")

print("Camera matrix:\n", camera_matrix)
print("Distortion coefficients:\n", dist_coeffs)