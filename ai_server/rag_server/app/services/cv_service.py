"""
CV 모델 서비스 - 모듈 → 이상 순으로 실행 (기기 정보는 device_monitor에서 참조)
"""

import cv2
import numpy as np
from typing import Dict, Any, List
from loguru import logger

from app.services.cv.device_monitor import current_device_type
from app.services.cv.module_detector import detect_modules_from_recent_frames
from app.services.cv.anomaly_detector import run_anomaly_detection


# -------------------------------
# Sharpness 계산 함수
# -------------------------------
def calculate_sharpness(frame: np.ndarray) -> float:
    """Laplacian variance로 sharpness 계산"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


# -------------------------------
# 메인 CV 파이프라인
# -------------------------------
async def run_cv_model(frames: List[np.ndarray]) -> Dict[str, Any]:
    """
    Wakeword 감지 이후 실행되는 CV 파이프라인
    - sharpness 높은 프레임만 사용
    - YOLO: 모듈 탐지
    - 이상 탐지 오케스트레이터 호출
    """
    if not frames:
        return {"detected": False, "message": "입력 프레임이 없습니다."}

    try:
        # ------------------------------------------
        # ① 현재 기기 타입 확인
        # ------------------------------------------
        device_type = current_device_type or "unknown"
        logger.info(f"[CV] 현재 기기 타입: {device_type}")

        # ------------------------------------------
        # ② 프레임 sharpness 평가 및 필터링
        # ------------------------------------------
        sharpness_scores = [(i, calculate_sharpness(f)) for i, f in enumerate(frames)]
        sharpness_scores.sort(key=lambda x: x[1], reverse=True)

        # 가장 선명한 프레임만 선택 (top 1~3)
        sharp_frames = [frames[i] for i, s in sharpness_scores[:3] if s > 50.0]
        if not sharp_frames:
            logger.warning("[CV] 모든 프레임이 흐릿하여 분석 스킵 (sharpness < 50)")
            return {
                "detected": False,
                "device_type": device_type,
                "modules": [],
                "anomalies": [],
                "message": "프레임 화질이 낮아 분석 불가"
            }

        logger.info(f"[CV] Sharpness 상위 프레임 선택: {len(sharp_frames)}장")

        # ------------------------------------------
        # ③ 모듈 탐지 및 이상 탐지 (AHU인 경우에만 수행)
        # ------------------------------------------
        modules = []
        anomalies = None
        
        # AHU인 경우에만 모듈 탐지와 이상 탐지 수행
        if device_type.upper() == "AHU":
            logger.info(f"[CV] {device_type} 감지됨 → 모듈 및 이상 탐지 수행")
            modules, anomalies, has_anomaly, msg = await _run_cv_pipeline(
                sharp_frames,
                device_type,
            )
        else:
            # AHU가 아닌 경우 모듈 탐지와 이상 탐지 스킵
            logger.info(f"[CV] {device_type}는 AHU가 아니므로 모듈 탐지와 이상 탐지를 스킵합니다.")
            has_anomaly = False
            msg = f"{device_type}는 CV 분석 대상이 아닙니다."

        # ------------------------------------------
        # ⑤ 최종 결과 반환
        # ------------------------------------------
        return {
            "detected": has_anomaly,
            "device_type": device_type,
            "modules": modules,
            "anomalies": anomalies if anomalies else {},
            "message": msg,
        }

    except Exception as e:
        logger.exception(f"[CV] 파이프라인 전체 오류: {e}")
        return {
            "detected": False,
            "device_type": current_device_type or "unknown",
            "modules": [],
            "anomalies": [],
            "message": f"CV 파이프라인 오류: {e}",
        }


async def _run_cv_pipeline(
    frames: List[np.ndarray],
    device_type: str,
):
    """
    실제 모듈 탐지 및 이상 분석을 수행하는 보조 함수.
    """
    modules = await detect_modules_from_recent_frames([frames[0]])
    if not modules:
        logger.warning(f"[CV] {device_type} 내부 모듈 탐지 실패")
        return modules, {}, False, f"{device_type} 내부 모듈 탐지 실패"

    logger.info(f"[CV] 모듈 탐지 완료: {modules}")

    anomalies = await run_anomaly_detection(frames, modules)

    has_anomaly = False
    msg = "탐지된 이상이 없습니다."
    if anomalies and isinstance(anomalies, dict):
        status = anomalies.get("status", "")
        results = anomalies.get("results", {})

        if status == "anomaly_detected":
            has_anomaly = True
            msg = "이상이 감지되었습니다."
        elif isinstance(results, dict):
            for module_name, module_result in results.items():
                if isinstance(module_result, dict) and module_result.get("status") == "anomaly":
                    has_anomaly = True
                    msg = "이상이 감지되었습니다."
                    break

    logger.info(f"[CV] 이상 탐지 결과: {msg} (status={anomalies.get('status') if anomalies else 'None'})")

    return modules, anomalies, has_anomaly, msg
