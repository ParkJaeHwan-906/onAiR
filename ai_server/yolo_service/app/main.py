from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

from ai_server.yolo_service.yolo_utils import load_yolo_model, yolo_infer


class ModelInfo(Dict[str, Optional[object]]):
    model: Optional[object]
    loaded: bool
    error: Optional[str]


app = FastAPI(title="YOLO Inference Service", version="0.1.0")

# 모델 파일 경로: yolo_service/models/
<<<<<<< HEAD
BASE_DIR = Path(__file__).resolve().parents[1]  # /app/ai_server/yolo_service/
=======
BASE_DIR = Path(__file__).resolve().parents[2]  # /app/ai_server/yolo_service/
>>>>>>> f1f39495291412014c2207d9f91d7ece5d4c5357
MODEL_DIR = BASE_DIR / "models"

MODEL_PATHS = {
    "device": MODEL_DIR / "device_best.pt",
    "module": MODEL_DIR / "module_best.pt",
    "panel": MODEL_DIR / "panel_best.pt",
}

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo-service")
_model_states: Dict[str, ModelInfo] = {
    name: {"model": None, "loaded": False, "error": None} for name in MODEL_PATHS
}
_model_lock = asyncio.Lock()


def _success_response(data: dict, status_code: int = 200):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
        },
    )


def _error_response(code: str, message: str, detail: Optional[dict] = None, status_code: int = 400):
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if detail:
        payload["error"]["detail"] = detail
    return JSONResponse(status_code=status_code, content=payload)


def _decode_image(data: bytes) -> Optional[np.ndarray]:
    if not data:
        return None
    np_array = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    return frame


async def _ensure_model(model_name: str):
    async with _model_lock:
        state = _model_states[model_name]
        if state["model"] is not None:
            return state["model"]
        if state["loaded"] and state["model"] is None:
            return None

        model_path = MODEL_PATHS[model_name]
        if not model_path.exists():
            logger.error(f"[yolo-service] 모델 파일을 찾을 수 없습니다: {model_path}")
            state["loaded"] = True
            state["error"] = "MODEL_NOT_FOUND"
            return None

        loop = asyncio.get_running_loop()

        def _load():
            return load_yolo_model(str(model_path))

        try:
            model = await loop.run_in_executor(_executor, _load)
        except Exception as exc:  # pragma: no cover
            logger.exception(f"[yolo-service] 모델 로드 실패({model_name}): {exc}")
            state["loaded"] = True
            state["error"] = str(exc)
            return None

        state["model"] = model
        state["loaded"] = True
        state["error"] = None
        logger.info(f"[yolo-service] '{model_name}' 모델 로드 완료")
        return model


async def _run_inference(model_name: str, frame: np.ndarray, return_boxes: bool = False):
    model = await _ensure_model(model_name)
    if model is None:
        raise RuntimeError(f"MODEL_NOT_READY:{model_name}")

    loop = asyncio.get_running_loop()
    infer_call = partial(yolo_infer, model, frame, return_boxes)
    return await loop.run_in_executor(_executor, infer_call)


def _aggregate_boxes(box_lists: List[List[dict]]) -> List[dict]:
    results: Dict[str, dict] = {}
    for boxes in box_lists:
        for box in boxes:
            label = box.get("label")
            confidence = float(box.get("confidence", 0.0))
            if label is None:
                continue
            if label not in results or confidence > results[label]["confidence"]:
                results[label] = {
                    "label": label,
                    "confidence": confidence,
                    "box": box.get("box"),
                }
    return list(results.values())


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("[yolo-service] shutting down executor")
    _executor.shutdown(wait=False)


@app.get("/health")
async def health():
    status = {
        name: state["model"] is not None
        for name, state in _model_states.items()
    }
    response = {"ready": True, **status}
    for name, state in _model_states.items():
        if state.get("error"):
            response[f"{name}_error"] = state["error"]
    return response


@app.post("/infer/device")
async def infer_device(file: UploadFile = File(...)):
    data = await file.read()
    frame = _decode_image(data)
    if frame is None:
        return _error_response("YOLO_BAD_REQUEST", "잘못된 이미지 데이터")

    try:
        result = await _run_inference("device", frame, return_boxes=True)
    except RuntimeError as exc:
        code = str(exc).split(":", 1)[0]
        return _error_response(code, "YOLO 모델이 준비되지 않았습니다.", {"model": "device"})
    except Exception as exc:  # pragma: no cover
        logger.exception("[yolo-service] device inference error: %s", exc)
        return _error_response("YOLO_INFERENCE_ERROR", "YOLO 추론 중 오류", {"detail": str(exc)}, 500)

    if not result:
        payload = {"label": None, "confidence": 0.0, "detections": []}
        return _success_response(payload)

    top_detection = max(result, key=lambda x: x.get("confidence", 0.0))
    payload = {
        "label": top_detection.get("label"),
        "confidence": float(top_detection.get("confidence", 0.0)),
        "detections": result,
    }
    return _success_response(payload)


@app.post("/infer/module")
async def infer_module(files: List[UploadFile] = File(...)):
    if not files:
        return _error_response("YOLO_BAD_REQUEST", "프레임이 제공되지 않았습니다.")

    frames: List[np.ndarray] = []
    for upload in files:
        data = await upload.read()
        frame = _decode_image(data)
        if frame is None:
            return _error_response("YOLO_BAD_REQUEST", f"잘못된 이미지 데이터: {upload.filename}")
        frames.append(frame)

    detections_all: List[List[dict]] = []

    for frame in frames:
        try:
            boxes = await _run_inference("module", frame, return_boxes=True)
        except RuntimeError as exc:
            code = str(exc).split(":", 1)[0]
            return _error_response(code, "YOLO 모델이 준비되지 않았습니다.", {"model": "module"})
        except Exception as exc:  # pragma: no cover
            logger.exception("[yolo-service] module inference error: %s", exc)
            return _error_response("YOLO_INFERENCE_ERROR", "YOLO 추론 중 오류", {"detail": str(exc)}, 500)

        detections_all.append(boxes or [])

    aggregated = _aggregate_boxes(detections_all)
    payload = {
        "frames": detections_all,
        "top_detections": aggregated,
    }
    return _success_response(payload)


@app.post("/infer/panel")
async def infer_panel(file: UploadFile = File(...)):
    data = await file.read()
    frame = _decode_image(data)
    if frame is None:
        return _error_response("YOLO_BAD_REQUEST", "잘못된 이미지 데이터")

    try:
        boxes = await _run_inference("panel", frame, return_boxes=True)
    except RuntimeError as exc:
        code = str(exc).split(":", 1)[0]
        return _error_response(code, "YOLO 모델이 준비되지 않았습니다.", {"model": "panel"})
    except Exception as exc:  # pragma: no cover
        logger.exception("[yolo-service] panel inference error: %s", exc)
        return _error_response("YOLO_INFERENCE_ERROR", "YOLO 추론 중 오류", {"detail": str(exc)}, 500)

    payload = {
        "detections": boxes or [],
    }
    return _success_response(payload)

