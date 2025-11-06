import cv2


video_path = "fan_spin.mp4"

frame = cv2.VideoCapture(video_path).read()[1]
frame = cv2.resize(frame, (640, 480))
r = cv2.selectROI("Select ROI", frame, False, False)
print("ROI:", r)
