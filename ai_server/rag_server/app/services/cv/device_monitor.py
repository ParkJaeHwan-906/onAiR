"""
기기 타입 모니터 (YOLO 기반)
- 백그라운드에서 최신 프레임 1장만 가져와서 YOLO 실행
- 프레임은 저장하지 않고 버림
- 탐지된 장비 타입만 전역변수(current_device_type)에 저장
"""

import asyncio
import torch
import numpy as np
import cv2
import os
from pathlib import Path
from app.services.cv.frame_collector import collect_latest_n_frames
from app.services.cv.yolo_executor import (
    acquire_yolo_context,
    wait_for_device_monitor_slot,
)
from app.services.cv.yolo_utils import load_yolo_model, yolo_infer

# 현재 감지된 장비 타입 (다른 서비스에서 참조)
current_device_type: str = "unknown"

# YOLO 모델 전역 캐시
_yolo_device_model = None


async def background_device_detector():
    """
    백그라운드에서 주기적으로 프레임 스트림의 최신 프레임 1장을 가져와 장비 타입 탐지
    - 프레임은 저장하지 않고 버림
    - 탐지된 장비 타입만 전역변수에 저장
    """
    global current_device_type, _yolo_device_model

    # YOLO 모델 로드 (한 번만)
    if _yolo_device_model is None:
        try:
            model_path = "/app/models/device_best.pt"
            if not Path(model_path).exists():
                print(f"⚠️ [device_monitor] 모델 파일이 없습니다: {model_path}")
                _yolo_device_model = False
            else:
                _yolo_device_model = load_yolo_model(model_path)
                print("✅ [device_monitor] YOLO 장비 모델 로드 완료")
        except Exception as e:
            print(f"❌ [device_monitor] YOLO 모델 로드 실패: {e}")
            _yolo_device_model = False

    print("✅ [device_monitor] 장비 모니터링 시작됨 (주기: 2초)")

    while True:
        try:
            await wait_for_device_monitor_slot()

            # 1️⃣ 최신 프레임 1장만 가져오기 (저장 안하고 바로 사용)
            frames = await collect_latest_n_frames(n=1)
            if not frames:
                await asyncio.sleep(2)
                continue

            # 2️⃣ YOLO로 장비 타입 탐지 (프레임은 처리 후 버림)
            latest_frame = frames[0]  # 최신 프레임 1장만 사용
            
            if not _yolo_device_model:
                print("⏭️ [device_monitor] YOLO 모델이 로드되지 않아 탐지를 스킵합니다.")
            else:
                async with acquire_yolo_context() as ctx:
                    device_label = await ctx.run(yolo_infer, _yolo_device_model, latest_frame)
                if device_label:
                    current_device_type = device_label  # 전역변수에 장비 명칭만 저장
                    print(f"🔍 [device_monitor] 감지된 장비: {device_label}")
                else:
                    print("⚠️ [device_monitor] 장비 탐지 실패, 이전 상태 유지")
            
            # 프레임은 여기서 버려짐 (저장 안함)

        except Exception as e:
            print(f"❌ [device_monitor] 오류 발생: {e}")

        # 2초 주기로 재시도
        await asyncio.sleep(2)


# _select_sharpest_frame 함수 제거됨 (최신 프레임 1장만 사용하므로 불필요)
