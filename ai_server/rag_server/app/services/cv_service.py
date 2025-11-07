"""
CV 모델 서비스 (보류 상태)
CV 모델이 통합되면 여기에 구현할 예정
"""
import asyncio
from typing import Optional, Dict, Any

async def run_cv_model() -> Dict[str, Any]:
    """
    CV 모델 실행 (보류 상태)
    
    Returns:
        {
            "detected": bool,  # 오류 탐지 여부
            "error_type": Optional[str],  # 오류 타입 (탐지된 경우)
            "confidence": float,  # 탐지 신뢰도
            "message": str  # 메시지
        }
    """
    # TODO: CV 모델 통합 후 구현
    # 현재는 항상 탐지 실패로 반환 (테스트용)
    await asyncio.sleep(0.1)  # 비동기 처리 시뮬레이션
    
    return {
        "detected": False,
        "error_type": None,
        "confidence": 0.0,
        "message": "CV 모델이 통합되지 않아 오류를 탐지하지 못했습니다."
    }

