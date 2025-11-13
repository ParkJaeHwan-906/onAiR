"""
YOLO 모델 파이프라인 최적화
- 모델을 미리 로드 (warm-up)
- 각 모델을 별도 스레드에서 병렬 실행 가능
- 프레임 스트림을 효율적으로 처리
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Callable, Any
import numpy as np
from loguru import logger

# 모델별 전용 스레드 풀 (병렬 처리 가능)
_device_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo-device")
_module_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo-module")
_panel_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo-panel")

# 모델 캐시 (미리 로드)
_model_cache: Dict[str, Any] = {}


def warmup_models():
    """모든 YOLO 모델을 미리 로드 (warm-up)"""
    global _model_cache
    
    try:
        # device_best.pt
        from app.services.cv.yolo_utils import load_yolo_model
        _model_cache["device"] = load_yolo_model("/app/models/device_best.pt")
        logger.info("✅ Device 모델 warm-up 완료")
    except Exception as e:
        logger.warning(f"⚠️ Device 모델 warm-up 실패: {e}")
        _model_cache["device"] = None
    
    try:
        # module_best.pt
        from ultralytics import YOLO
        _model_cache["module"] = YOLO("/app/models/module_best.pt")
        _model_cache["module"].fuse()
        logger.info("✅ Module 모델 warm-up 완료")
    except Exception as e:
        logger.warning(f"⚠️ Module 모델 warm-up 실패: {e}")
        _model_cache["module"] = None
    
    try:
        # panel_best.pt
        _model_cache["panel"] = YOLO("/app/models/panel_best.pt")
        logger.info("✅ Panel 모델 warm-up 완료")
    except Exception as e:
        logger.warning(f"⚠️ Panel 모델 warm-up 실패: {e}")
        _model_cache["panel"] = None


async def run_device_detection(frame: np.ndarray) -> Optional[str]:
    """
    장비 타입 탐지 (별도 스레드에서 실행)
    """
    if _model_cache.get("device") is None:
        return None
    
    loop = asyncio.get_running_loop()
    from app.services.cv.yolo_utils import yolo_infer
    
    def _infer():
        return yolo_infer(_model_cache["device"], frame)
    
    return await loop.run_in_executor(_device_executor, _infer)


async def run_module_detection(frames: List[np.ndarray]) -> List[Dict[str, Any]]:
    """
    모듈 탐지 (별도 스레드에서 실행)
    """
    if _model_cache.get("module") is None:
        return []
    
    loop = asyncio.get_running_loop()
    model = _model_cache["module"]
    
    def _detect():
        detections = []
        for frame in frames:
            results = model.predict(frame, imgsz=640, conf=0.35, verbose=False)
            for res in results:
                for box in res.boxes:
                    label = model.names[int(box.cls)]
                    conf = float(box.conf)
                    detections.append({"label": label, "confidence": conf})
        return detections
    
    detections = await loop.run_in_executor(_module_executor, _detect)
    
    # 중복 제거 및 최고 신뢰도 선택
    from app.services.cv.module_detector import _filter_top_detections
    return _filter_top_detections(detections)


async def run_panel_detection(frame: np.ndarray) -> Dict[str, Any]:
    """
    제어판 탐지 (별도 스레드에서 실행)
    """
    if _model_cache.get("panel") is None or _model_cache.get("module") is None:
        return {"status": "error", "message": "모델이 로드되지 않음"}
    
    loop = asyncio.get_running_loop()
    module_model = _model_cache["module"]
    panel_model = _model_cache["panel"]
    
    def _detect():
        # Module 모델로 패널 ROI 추출
        module_results = module_model.predict(frame, conf=0.5, device="cpu", verbose=False)
        panel_roi = None
        for r in module_results:
            for box in r.boxes:
                cls = module_model.names[int(box.cls)]
                if "panel" in cls.lower():
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    panel_roi = frame[y1:y2, x1:x2]
                    break
        if panel_roi is None or panel_roi.size == 0:
            return {"status": "not_found", "message": "제어판 미검출"}
        
        # Panel 모델로 LED/온도 분석
        button_results = panel_model.predict(panel_roi, conf=0.5, device="cpu", verbose=False)
        # ... (나머지 로직)
        return {"status": "done", "results": {}}
    
    return await loop.run_in_executor(_panel_executor, _detect)


def shutdown_executors():
    """모든 executor 종료"""
    _device_executor.shutdown(wait=False)
    _module_executor.shutdown(wait=False)
    _panel_executor.shutdown(wait=False)

