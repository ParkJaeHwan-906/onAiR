import cv2
import requests
import argparse
import os

YOLO_URL = os.getenv("YOLO_SERVICE_URL", "http://127.0.0.1:9000")

YOLO_ENDPOINTS = {
    "device": "/infer/device",
    "module": "/infer/module",
    "panel": "/infer/panel",
}


def run_yolo(image_path: str, yolo_type: str):
    url = YOLO_URL + YOLO_ENDPOINTS[yolo_type]
    print(f"[INFO] YOLO 호출: {url}")

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"이미지를 불러올 수 없습니다: {image_path}")

    _, img_encoded = cv2.imencode(".jpg", img)
    files = {"file": ("image.jpg", img_encoded.tobytes(), "image/jpeg")}

    resp = requests.post(url, files=files)
    if resp.status_code != 200:
        print(f"[ERROR] YOLO 실패: {resp.status_code}")
        print(resp.text)
        return

    print("[RESULT]")
    print(resp.json())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--type", type=str, required=True, choices=["device", "module", "panel"])
    args = parser.parse_args()

    run_yolo(args.image, args.type)
