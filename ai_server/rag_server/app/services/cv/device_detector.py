# app/services/cv/device_monitor.py
import asyncio
import time
from app.services.cv.device_detector import detect_device_type

current_device_type = "unknown"  # 최근 탐지 결과를 메모리에 유지

async def background_device_detector(frame_source):
    global current_device_type
    while True:
        frame = frame_source.get_latest_frame()
        if frame is not None:
            detected = await detect_device_type(frame)
            if detected:
                current_device_type = detected
        await asyncio.sleep(2)  # 주기 (조절 가능)
