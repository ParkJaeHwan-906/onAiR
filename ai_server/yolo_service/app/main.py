# ai_server/yolo_service/main.py
import asyncio
from fastapi import FastAPI
from loguru import logger

from ai_server.yolo_service.device_detector import start_device_detector
from ai_server.yolo_service.redis_client import get_device_state
from ai_server.yolo_service.anomaly import run_anomaly_detection

app = FastAPI(title="YOLO Worker Service", version="1.0")

device_detector_task = None
detector_lock = asyncio.Lock()


@app.get("/health")
async def health():
    state = await get_device_state()
    return {"status": "ok", "device_state": state}


@app.on_event("startup")
async def startup():
    """
    서버 시작 시 Device Detector 자동 실행
    """
    global device_detector_task
    async with detector_lock:
        logger.info("▶ Device Detector 자동 시작")
        device_detector_task = asyncio.create_task(start_device_detector())


async def stop_device_detector_task():
    """
    외부에서 호출할 수 있는 안전한 stop 함수
    (socket_handler 등에서 wakeword 감지 시 호출)
    """
    global device_detector_task

    async with detector_lock:
        if device_detector_task:
            logger.info("⏸ Device Detector 중지 요청")
            device_detector_task.cancel()

            try:
                await device_detector_task
            except asyncio.CancelledError:
                logger.info("⛔ Device Detector 완전 종료됨")

            device_detector_task = None


@app.on_event("shutdown")
async def shutdown():
    """
    FastAPI 서버 종료 시 Device Detector도 정리함
    """
    await stop_device_detector_task()
    logger.info("🛑 서버 종료: Device Detector 종료 완료")


@app.post("/analyze")
async def analyze(payload: dict):
    device_detector_task.cancel()
    result = run_anomaly_detection()
    return result

@app.post("/device/start")
async def start_device():
    global device_detector_task
    async with detector_lock:
        if not device_detector_task:
            device_detector_task = asyncio.create_task(start_device_detector())
            return {"status": "started"}
        return {"status": "already_running"}


@app.post("/device/stop")
async def stop_device():
    await stop_device_detector_task()
    return {"status": "stopped"}