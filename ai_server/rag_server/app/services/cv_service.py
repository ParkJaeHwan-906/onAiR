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
    print(f"📡 [CV Service] YOLO 서비스 요청 시작")
    print(f"   URL: {url}")
    print(f"   YOLO_SERVICE_URL: {YOLO_URL}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print(f"   요청 전송 중...")
            res = await client.post(url, json={"trigger": "run"})
            print(f"   응답 상태 코드: {res.status_code}")
            res.raise_for_status()
            result = res.json()
            print(f"✅ [CV Service] YOLO 서비스 응답 수신 완료")
            print(f"   응답 데이터 키: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            return result
    except httpx.TimeoutException as e:
        print(f"❌ [CV Service] YOLO 서비스 요청 타임아웃: {e}")
        raise
    except httpx.HTTPStatusError as e:
        print(f"❌ [CV Service] YOLO 서비스 HTTP 오류: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        print(f"❌ [CV Service] YOLO 서비스 요청 오류: {e}")
        import traceback
        traceback.print_exc()
        raise

