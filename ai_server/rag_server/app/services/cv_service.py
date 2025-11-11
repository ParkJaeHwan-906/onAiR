"""
CV 모델 서비스 - 모듈 → 이상 순으로 실행 (기기 정보는 device_monitor에서 참조)
"""

import asyncio
from typing import Dict, Any, List
import torch

from app.services.cv.device_monitor import current_device_type
from app.services.cv.module_detector import detect_modules_from_recent_frames
from app.services.cv.anomaly_detector import run_anomaly_detection

# PyTorch CPU 스레드 제한 (서버 안정화용)
torch.set_num_threads(2)
torch.set_num_interop_threads(2)


async def run_cv_model(frames: List) -> Dict[str, Any]:
    """Wakeword 감지 이후 실행되는 CV 파이프라인"""
    if not frames:
        return {"detected": False, "message": "입력 프레임이 없습니다."}

    try:
        # ------------------------------------------
        # ① 기기 정보 참조 (이미 background에서 갱신 중)
        # ------------------------------------------
        device_type = current_device_type or "unknown"

        # ------------------------------------------
        # ② 모듈 탐지
        # ------------------------------------------
        recent_frames = frames[-5:] if len(frames) >= 5 else frames
        modules = await detect_modules_from_recent_frames(recent_frames)

        if not modules:
            return {
                "detected": False,
                "device_type": device_type,
                "modules": [],
                "anomalies": [],
                "message": f"{device_type} 내부 모듈 탐지 실패"
            }

        # ------------------------------------------
        # ③ 이상 탐지
        # ------------------------------------------
        anomaly_frames = frames[-3:] if len(frames) >= 3 else frames
        anomalies = await run_anomaly_detection(anomaly_frames, modules)

        has_anomaly = bool(anomalies and len(anomalies) > 0)
        message = "이상이 감지되었습니다." if has_anomaly else "탐지된 이상이 없습니다."

        return {
            "detected": has_anomaly,
            "device_type": device_type,
            "modules": modules,
            "anomalies": anomalies,
            "message": message,
        }

    except Exception as e:
        return {
            "detected": False,
            "device_type": current_device_type or "unknown",
            "modules": [],
            "anomalies": [],
            "message": f"CV 파이프라인 오류: {e}",
        }
