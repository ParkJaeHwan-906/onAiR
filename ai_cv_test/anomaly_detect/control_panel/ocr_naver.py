import requests
import uuid
import time
import json

API_URL = "https://x52x77omzp.apigw.ntruss.com/custom/v1/47790/fbbf789284183519ee095b5fe46ee9b1729281fc50869acac4f3e7db3dea9732/general"
SECRET_KEY = "eWxoVXJneUNVcnN2YXdqYk91WXVYc3BMVVBUVXRUZFY="

def call_clova_ocr(image_path):
    # 요청 메시지 정의
    request_json = {
        "images": [
            {
                "format": "jpg",
                "name": "demo"
            }
        ],
        "requestId": str(uuid.uuid4()),
        "version": "V2",
        "timestamp": int(time.time() * 1000)
    }

    headers = {
        "X-OCR-SECRET": SECRET_KEY
    }

    files = {
        "message": (None, json.dumps(request_json), "application/json"),
        "file": (image_path, open(image_path, "rb"), "image/jpeg")
    }

    response = requests.post(API_URL, headers=headers, files=files)
    return response.json()

# 실행 예시
result = call_clova_ocr("./controller.jpeg")
print(json.dumps(result, indent=2, ensure_ascii=False))
