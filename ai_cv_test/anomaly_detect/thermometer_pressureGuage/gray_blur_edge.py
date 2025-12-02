import cv2
import os

def preprocess_debug(roi, out_dir="debug_step02"):
    os.makedirs(out_dir, exist_ok=True)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(f"{out_dir}/01_gray.png", gray)

    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    cv2.imwrite(f"{out_dir}/02_blur.png", blur)

    edges = cv2.Canny(blur, 50, 150)
    cv2.imwrite(f"{out_dir}/03_edges.png", edges)

    print("saved:", out_dir)
    return gray, blur, edges


if __name__ == "__main__":
    roi = cv2.imread("roi_debug/roi_167_42.png")  # 방금 YOLO로 자른 파일명
    gray, blur, edges = preprocess_debug(roi)