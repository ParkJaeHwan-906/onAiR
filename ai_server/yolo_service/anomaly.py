import asyncio
from loguru import logger
from typing import Dict, List

from yolo_service.redis_frame_store import get_cv_buffer_frames, get_device_state

# 개별 anomaly 분석 모듈
from yolo_service.fan_belt_anomaly import analyze_fan_belt
from yolo_service.gauge_anomaly import analyze_gauge
from yolo_service.panel_anomaly import analyze_panel


async def run_anomaly_detection() -> Dict:
    """
    AHU 전용 이상탐지 통합 로직
    - Redis에서 최근 프레임 읽기
    - fan_belt / gauge / panel 모두 실행
    - 각 모듈 결과 통합하여 이상 여부 판단
    """
    logger.info("🚀 run_anomaly_detection() 시작")

    # 1. 장비 타입 확인 (AHU만 지원)
    device_label = await get_device_state()
    if device_label != "AHU":
        logger.warning(f"⚠️ AHU가 아님 → 분석 중단 (감지된 장비: {device_label})")
        return {
            "detected": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "message": "지원하지 않는 장비입니다."
        }

    # 2. Redis에서 프레임 버퍼 가져오기
    frames = await get_cv_buffer_frames(n=10)
    if not frames:
        logger.warning("⚠️ 분석할 프레임이 없습니다.")
        return {
            "detected": False,
            "device_type": device_label,
            "modules": [],
            "anomalies": {},
            "message": "분석할 프레임이 없습니다."
        }

    # 3. 개별 anomaly 모듈 실행
    fan_belt_result = await analyze_fan_belt(frames)
    gauge_result = await analyze_gauge(frames)
    panel_result = await analyze_panel(frames)

    anomalies = {
        "fan_belt": fan_belt_result,
        "gauge": gauge_result,
        "panel": panel_result,
    }

    # 4. anomaly 판단
    def is_anomaly(r: dict):
        if not r:
            return False
        return r.get("status") == "anomaly"

    has_anomaly = any(is_anomaly(r) for r in anomalies.values())

    # 5. 모듈 목록 정리 (status가 의미 있는 모듈만)
    modules = []
    for name, res in anomalies.items():
        if not res:
            continue
        if res.get("status") in ("not_found", "unknown", "error"):
            continue
        modules.append({"label": name, "confidence": 1.0})

    # 6. 결과 통합
    result = {
        "detected": has_anomaly,
        "device_type": device_label,
        "modules": modules,
        "anomalies": {
            "status": "anomaly_detected" if has_anomaly else "no_anomaly",
            "results": anomalies
        },
        "message": "이상이 탐지되었습니다." if has_anomaly else "이상이 탐지되지 않았습니다."
    }

    logger.info(f"📦 run_anomaly_detection() 최종 결과: {result}")
    return result


if __name__ == "__main__":
    print(asyncio.run(run_anomaly_detection()))
