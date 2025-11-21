# app/services/cv_service.py
"""
CV (Computer Vision) 서비스
YOLO 이상 탐지 실행
"""
import os
import httpx
from typing import Dict, Any

YOLO_URL = os.getenv("YOLO_SERVICE_URL", "http://vision:9000")


async def run_anomaly_detection() -> Dict[str, Any]:
    """
    YOLO 이상 탐지 실행
    
    Returns:
        dict: CV 탐지 결과
    """
    url = f"{YOLO_URL}/analyze"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(url, json={"trigger": "run"})
        res.raise_for_status()
        return res.json()

