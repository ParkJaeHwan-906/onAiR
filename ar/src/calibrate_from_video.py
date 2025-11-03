import cv2
import numpy as np
import os

# === 체스보드 내부 코너 수 ===
# 예: 9x11 칸이면 (8,10)
pattern_size = (10, 7)
square_size = 1.0  # 한 칸의 실제 크기 (상대 단위)

video_path = "../data/calibration_video.mp4"
output_dir = "../output/calibration"
os.makedirs(output_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)

# === 3D, 2D 포인트 저장 리스트 ===
objpoints = []  # 3D world 좌표
imgpoints = []  # 2D image 좌표

# === 체스보드 한 장의 실제 3D 좌표 구성 ===
objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
objp *= square_size

# === 감지 파라미터 ===
frame_interval = 10
success_count = 0
max_frames = 30
frame_idx = 0

flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE

print("🎥 Calibration 시작...")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame_idx += 1

    # 🔹 프레임 건너뛰기
    if frame_idx % frame_interval != 0:
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    ret_corners, corners = cv2.findChessboardCorners(gray, pattern_size, flags)

    if ret_corners:
        cv2.cornerSubPix(gray, corners, (11,11), (-1,-1),
                         (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))

        objpoints.append(objp)
        imgpoints.append(corners)

        cv2.drawChessboardCorners(frame, pattern_size, corners, ret_corners)
        success_count += 1
        print(f"✅ {frame_idx}프레임 감지 성공 ({success_count}/{max_frames})")

        if success_count >= max_frames:
            print("✅ 충분한 데이터 확보. 캘리브레이션 시작합니다.")
            break
    else:
        print(f"❌ {frame_idx}프레임 감지 실패")

    cv2.imshow("Calibration", cv2.resize(frame, (960, 540)))
    if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
        break

cap.release()
cv2.destroyAllWindows()

# === 카메라 보정 수행 ===
if len(objpoints) >= 5:
    print("📸 카메라 파라미터 계산 중...")
    ret, K, D, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

    print("\n=== ✅ 결과 ===")
    print("평균 reprojection error:", ret)
    print("\n카메라 행렬 K:\n", K)
    print("\n왜곡 계수 D:\n", D)

    np.save(os.path.join(output_dir, "camera_intrinsics.npy"), K)
    np.save(os.path.join(output_dir, "dist_coeffs.npy"), D)

    print(f"\n💾 저장 완료 → {output_dir}")
else:
    print("⚠️ 체스보드 감지 횟수가 부족하여 보정 불가.")
