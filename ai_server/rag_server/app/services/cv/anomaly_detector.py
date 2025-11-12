"""
이상 탐지 오케스트레이터 (Fallback 구조 포함)
fan/belt / gauge / panel 분석 결과를 통합하고,
CV 탐지 불가 시 fallback 경로(대화 기반 구체화 요청)를 반환한다.
"""

import asyncio
from typing import List, Dict, Any
from loguru import logger


from app.services.cv.sub_anomaly.fan_belt_anomaly import analyze_fan_belt
from app.services.cv.sub_anomaly.gauge_anomaly import analyze_gauge
from app.services.cv.sub_anomaly.panel_anomaly import analyze_panel


async def run_anomaly_detection(frames: List, modules: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    fan/belt + gauge + panel 병렬 실행 후 결과 통합
    - fan/belt: Optical Flow 기반 (20프레임 이상 필요)
    - gauge: 지침 각도 기반 (단일 프레임)
    - panel: LED 점등 상태 기반 (단일 프레임)
    - fallback: 탐지 불확실하거나 결과가 없는 경우 대화로 구체화 요청
    Args:
        frames: 최근 프레임 리스트
        modules: 이전 단계 모듈 탐지 결과 (fan, gauge, panel 등)
    """
    if not frames:
        logger.warning("[anomaly_detector] 입력 프레임이 비어 있음.")
        return {
            "status": "no_frames",
            "message": "입력 프레임이 없습니다.",
            "fallback_required": True,
            "fallback": [{"type": "vision_missing", "reason": "no_input"}],
        }

    try:
        # ------------------------------------------
        # 분석 대상 모듈 필터링
        # ------------------------------------------
        target_types = _select_target_modules(modules)

        logger.info(f"[anomaly_detector] 분석 대상 모듈: {target_types}")

        # ------------------------------------------
        # 병렬 실행 (비동기 + CPU-safe)
        # ------------------------------------------
        tasks = []
        if "fan" in target_types or "belt" in target_types:
            tasks.append(analyze_fan_belt(frames))
        if "gauge" in target_types:
            tasks.append(analyze_gauge(frames))
        if "panel" in target_types:
            tasks.append(analyze_panel(frames))

        if not tasks:
            logger.warning("[anomaly_detector] 실행할 분석 모듈 없음.")
            return {
                "status": "no_targets",
                "message": "탐지된 모듈이 없어 분석을 수행하지 않았습니다.",
                "fallback_required": True,
                "fallback": [{"type": "no_module", "reason": "no_detected_modules"}],
            }

        results = await asyncio.gather(*tasks, return_exceptions=False)

        # ------------------------------------------
        # 결과 통합 및 fallback 판단
        # ------------------------------------------
        fallback_triggers = []
        result_map = {}

        for r in results:
            if not r:
                continue
            r_type = r.get("type", "unknown")
            result_map[r_type] = r

            if r.get("status") in ("unknown", "not_found", "low_confidence"):
                fallback_triggers.append({
                    "type": r_type,
                    "reason": r.get("message", "분석 불가"),
                })

        has_fallback = len(fallback_triggers) > 0
        
        # 이상 탐지 여부 확인 (results 중 하나라도 status="anomaly"인지)
        has_anomaly_detected = False
        for module_result in result_map.values():
            if isinstance(module_result, dict) and module_result.get("status") == "anomaly":
                has_anomaly_detected = True
                break
        
        # overall_status 결정
        if has_anomaly_detected:
            overall_status = "anomaly_detected"  # 이상 탐지 성공
        elif has_fallback:
            overall_status = "partial_fail"  # 부분 실패 (fallback 필요)
        else:
            overall_status = "done"  # 정상 완료 (이상 없음)

        # ------------------------------------------
        # 최종 결과
        # ------------------------------------------
        summary = {
            "status": overall_status,
            "results": result_map,
            "fallback_required": has_fallback,
            "fallback": fallback_triggers if has_fallback else None,
        }

        logger.info(f"[anomaly_detector] 결과 요약: {summary['status']} | fallback={has_fallback} | anomaly_detected={has_anomaly_detected}")
        return summary

    except Exception as e:
        logger.exception(f"[anomaly_detector] 오류 발생: {e}")
        return {
            "status": "error",
            "message": f"이상 탐지 중 오류 발생: {e}",
            "fallback_required": True,
            "fallback": [{"type": "system_error", "reason": str(e)}],
        }


def _select_target_modules(modules: List[Dict[str, Any]] = None) -> List[str]:
    """모듈 탐지 결과에서 분석할 대상만 추출"""
    if not modules:
        return []  # fallback
    labels = [m["label"].lower() for m in modules]
    targets = []
    if any("fan" in l or "belt" in l for l in labels):
        targets.extend(["fan", "belt"])
    if any("gauge" in l for l in labels):
        targets.append("gauge")
    if any("panel" in l for l in labels):
        targets.append("panel")
    return list(set(targets))
