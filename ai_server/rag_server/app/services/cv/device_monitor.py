"""
기기 타입 모니터 (YOLO 기반)
- 백그라운드에서 Redis의 최신 프레임을 주기적으로 확인
- 장비 타입을 감지하여 메모리에 유지
"""

import asyncio
import torch
import numpy as np
import cv2
from redis_util import get_latest_frames
from yolo_utils import load_yolo_model, yolo_infer

# 현재 감지된 장비 타입 (다른 서비스에서 참조)
current_device_type: str = "unknown"

# YOLO 모델 전역 캐시
_yolo_device_model = None

torch.set_num_threads(1)
torch.set_num_interop_threads(1)


async def background_device_detector():
    """
    백그라운드에서 주기적으로 Redis의 최신 프레임을 가져와 장비 타입 탐지
    """
    global current_device_type, _yolo_device_model

    # YOLO 모델 로드 (한 번만)
    if _yolo_device_model is None:
        _yolo_device_model = load_yolo_model("/app/models/device_best.pt")

    print("✅ [device_monitor] 장비 모니터링 시작됨 (주기: 2초)")

    while True:
        try:
            # 1️⃣ Redis에서 최근 프레임 5장 가져오기
            frames = await get_latest_frames(limit=5)
            if not frames:
                await asyncio.sleep(2)
                continue

            # 2️⃣ sharpness 기반으로 가장 선명한 프레임 선택
            sharpest_frame = _select_sharpest_frame(frames)
            if sharpest_frame is None:
                await asyncio.sleep(2)
                continue

            # 3️⃣ YOLO로 장비 타입 탐지
            device_label = yolo_infer(_yolo_device_model, sharpest_frame)
            if device_label:
                current_device_type = device_label
                print(f"🔍 [device_monitor] 감지된 장비: {device_label}")
            else:
                print("⚠️ [device_monitor] 장비 탐지 실패, 이전 상태 유지")

        except Exception as e:
            print(f"❌ [device_monitor] 오류 발생: {e}")

        # 2초 주기로 재시도
        await asyncio.sleep(2)


def _select_sharpest_frame(frames: list[np.ndarray]) -> np.ndarray:
    """Laplacian variance 기반으로 가장 선명한 프레임 선택"""
    if not frames:
        return None
    scores = []
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        scores.append(sharpness)
    idx = int(np.argmax(scores))
    return frames[idx]
