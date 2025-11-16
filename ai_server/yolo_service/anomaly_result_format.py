from datetime import datetime
from typing import Dict, Any


def build_anomaly_result(
    device_label: str,
    device_confidence: float,
    module_labels: list[str],
    frames_used: int,
    fan_result: Dict[str, Any],
    belt_result: Dict[str, Any],
    panel_result: Dict[str, Any],
    gauge_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    이상 탐지 통합 결과 생성
    """
    return {
        "status": "success",  # 추후 이상 없으면 fail로 조정 가능
        "device": {
            "label": device_label,
            "confidence": device_confidence,
            "timestamp": datetime.utcnow().isoformat()
        },
        "module": {
            "detected_modules": module_labels,
            "frames_used": frames_used
        },
        "anomaly": {
            "fan": fan_result,
            "belt": belt_result,
            "panel": panel_result,
            "gauge": gauge_result
        }
    }