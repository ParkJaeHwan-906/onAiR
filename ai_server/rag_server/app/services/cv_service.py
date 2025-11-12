"""
CV 모델 서비스 - 모듈 → 이상 순으로 실행 (기기 정보는 device_monitor에서 참조)
"""

import asyncio
import cv2
import numpy as np
import torch
from typing import Dict, Any, List
from loguru import logger

from cv.device_monitor import current_device_type
from cv.module_detector import detect_modules_from_recent_frames
from cv.anomaly_detector import run_anomaly_detection

# PyTorch CPU 스레드 제한 (서버 안정화용)
torch.set_num_threads(1)
torch.set_num_interop_threads(1)


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
        print(f"🔍 [CV] 현재 기기 타입 확인: {device_type}")

        # ------------------------------------------
        # ② 프레임 sharpness 평가 및 필터링
        # ------------------------------------------
        sharpness_scores = [(i, calculate_sharpness(f)) for i, f in enumerate(frames)]
        sharpness_scores.sort(key=lambda x: x[1], reverse=True)

        # 가장 선명한 프레임만 선택 (top 1~3)
        sharp_frames = [frames[i] for i, s in sharpness_scores[:3] if s > 50.0]
        if not sharp_frames:
            logger.warning("[CV] 모든 프레임이 흐릿하여 분석 스킵 (sharpness < 50)")
            print(f"⚠️ [CV] 모든 프레임이 흐릿하여 분석 스킵 (sharpness < 50)")
            print(f"   최고 sharpness: {max([s for _, s in sharpness_scores], default=0):.2f}")
            return {
                "detected": False,
                "device_type": device_type,
                "modules": [],
                "anomalies": [],
                "message": "프레임 화질이 낮아 분석 불가"
            }

        logger.info(f"[CV] Sharpness 상위 프레임 선택: {len(sharp_frames)}장")
        top_sharpness = max([s for _, s in sharpness_scores[:3]], default=0)
        print(f"✅ [CV] Sharpness 상위 프레임 선택: {len(sharp_frames)}장 (최고 sharpness: {top_sharpness:.2f})")

        # ------------------------------------------
        # ③ 모듈 탐지 및 이상 탐지 (AHU인 경우에만 수행)
        # ------------------------------------------
        modules = []
        anomalies = None
        
        # AHU인 경우에만 모듈 탐지와 이상 탐지 수행
        if device_type.upper() == "AHU":
            print(f"🔍 [CV] {device_type} 감지됨 → 모듈 탐지 및 이상 탐지 수행")
            try:
                print(f"📦 [CV] 모듈 탐지 시작 (YOLO 모델: module_best.pt)")
                modules = await detect_modules_from_recent_frames([sharp_frames[0]])  # 한 장만 사용
                if not modules:
                    logger.warning(f"[CV] {device_type} 내부 모듈 탐지 실패")
                    print(f"⚠️ [CV] {device_type} 내부 모듈 탐지 실패")
                    return {
                        "detected": False,
                        "device_type": device_type,
                        "modules": [],
                        "anomalies": [],
                        "message": f"{device_type} 내부 모듈 탐지 실패"
                    }
                logger.info(f"[CV] 모듈 탐지 완료: {modules}")
                module_names = [m.get('label', 'unknown') for m in modules]
                print(f"✅ [CV] 모듈 탐지 완료: {len(modules)}개 모듈 발견")
                print(f"   탐지된 모듈: {', '.join(module_names)}")
            except Exception as e:
                logger.exception(f"[CV] 모듈 탐지 중 오류: {e}")
                return {
                    "detected": False,
                    "device_type": device_type,
                    "modules": [],
                    "anomalies": [],
                    "message": f"모듈 탐지 오류: {e}"
                }

            # ------------------------------------------
            # ④ 이상 탐지 (fan/belt/gauge/panel 병렬)
            # ------------------------------------------
            try:
                print(f"🔍 [CV] 이상 탐지 시작 (병렬 실행: fan/belt, gauge, panel)")
                anomalies = await run_anomaly_detection(sharp_frames, modules)
                
                # 이상 탐지 결과 분석
                # anomalies.status가 "anomaly_detected"이거나, results 중 하나라도 status="anomaly"이면 이상 탐지 성공
                has_anomaly = False
                if anomalies and isinstance(anomalies, dict):
                    status = anomalies.get("status", "")
                    results = anomalies.get("results", {})
                    
                    print(f"📊 [CV] 이상 탐지 결과 분석")
                    print(f"   전체 상태: {status}")
                    print(f"   결과 모듈 수: {len(results) if isinstance(results, dict) else 0}개")
                    
                    # status가 "anomaly_detected"인 경우
                    if status == "anomaly_detected":
                        has_anomaly = True
                        print(f"   ✅ 이상 탐지 성공 (status='anomaly_detected')")
                    # results 중 하나라도 status="anomaly"인 경우
                    elif isinstance(results, dict):
                        for module_name, module_result in results.items():
                            if isinstance(module_result, dict) and module_result.get("status") == "anomaly":
                                has_anomaly = True
                                print(f"   ✅ 이상 탐지 성공: {module_name} 모듈에서 이상 발견")
                                break
                        if not has_anomaly:
                            print(f"   ℹ️ 모든 모듈 정상 상태")
                
                msg = "이상이 감지되었습니다." if has_anomaly else "탐지된 이상이 없습니다."

                logger.info(f"[CV] 이상 탐지 결과: {msg} (status={anomalies.get('status') if anomalies else 'None'})")
                print(f"✅ [CV] 이상 탐지 완료: {msg}")
            except Exception as e:
                logger.exception(f"[CV] 이상 탐지 중 오류: {e}")
                return {
                    "detected": False,
                    "device_type": device_type,
                    "modules": modules,
                    "anomalies": [],
                    "message": f"이상 탐지 오류: {e}",
                }
        else:
            # AHU가 아닌 경우 모듈 탐지와 이상 탐지 스킵
            logger.info(f"[CV] {device_type}는 AHU가 아니므로 모듈 탐지와 이상 탐지를 스킵합니다.")
            print(f"ℹ️ [CV] {device_type}는 AHU가 아니므로 모듈 탐지와 이상 탐지를 스킵합니다.")
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
