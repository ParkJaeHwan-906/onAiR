"""
이상 탐지 오케스트레이터 (Fallback 구조 포함)
fan/belt / gauge / panel 분석 결과를 통합하고,
CV 탐지 불가 시 fallback 경로(대화 기반 구체화 요청)를 반환한다.
"""

import asyncio
from typing import List, Dict, Any
from app.services.cv.sub_anomaly.fan_belt_anomaly import analyze_fan_belt
from app.services.cv.sub_anomaly.gauge_anomaly import analyze_gauge
from app.services.cv.sub_anomaly.panel_anomaly import analyze_panel


async def run_anomaly_detection(frames: List) -> Dict[str, Any]:
    """
    fan/belt + gauge + panel 병렬 실행 후 결과 통합
    - fan/belt: Optical Flow 기반 (20프레임 이상 필요)
    - gauge: 지침 각도 기반 (단일 프레임)
    - panel: LED 점등 상태 기반 (단일 프레임)
    - fallback: 탐지 불확실하거나 결과가 없는 경우 대화로 구체화 요청
    """
    if not frames:
        return {
            "status": "no_frames",
            "message": "입력 프레임이 없습니다.",
            "fallback_required": True,
            "fallback": [
                {"type": "vision_missing", "reason": "no_input"}
            ]
        }

    try:
        # ------------------------------
        # 병렬 실행
        # ------------------------------
        tasks = [
            analyze_fan_belt(frames),      # 여러 프레임 기반
            analyze_gauge(frames[-1]),     # 마지막 프레임
            analyze_panel(frames[-1])      # 마지막 프레임
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # ------------------------------
        # 결과 통합 및 fallback 판단
        # ------------------------------
        fallback_triggers = []
        result_map = {}

        for r in results:
            if not r:
                continue

            # 정상 결과 수집
            r_type = r.get("type", "unknown")
            result_map[r_type] = r

            # fallback 조건
            if r.get("status") in ("unknown", "not_found", "low_confidence"):
                fallback_triggers.append({
                    "type": r_type,
                    "reason": r.get("message", "분석 불가")
                })

        # ------------------------------
        # 최종 판단
        # ------------------------------
        has_fallback = len(fallback_triggers) > 0
        overall_status = "partial_fail" if has_fallback else "done"

        return {
            "status": overall_status,
            "results": result_map,
            "fallback_required": has_fallback,
            "fallback": fallback_triggers if has_fallback else None
        }

    except Exception as e:
        # 예외 처리 시 전체 fallback 반환
        return {
            "status": "error",
            "message": f"이상 탐지 중 오류 발생: {e}",
            "fallback_required": True,
            "fallback": [
                {"type": "system_error", "reason": str(e)}
            ]
        }
