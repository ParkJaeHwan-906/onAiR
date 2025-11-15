# ai_server/yolo_service/main.py
import asyncio
from fastapi import FastAPI
from loguru import logger

from ai_server.yolo_service.device_monitor import start_device_detector
from ai_server.yolo_service.redis_client import get_device_state
from ai_server.yolo_service.anomaly import run_anomaly_detection

app = FastAPI(title="YOLO Worker Service", version="1.0")

device_detector_task: asyncio.Task | None = None
detector_lock = asyncio.Lock()


# --------------------------------------------------------
# 건강 체크
# --------------------------------------------------------
@app.get("/health")
async def health():
    state = await get_device_state()
    return {"status": "ok", "device_state": state}


# --------------------------------------------------------
# 서버 시작: Device Detector 자동 실행
# --------------------------------------------------------
@app.on_event("startup")
async def startup():
    global device_detector_task
    async with detector_lock:
        if device_detector_task is None:
            logger.info("▶ Device Detector 자동 시작")
            device_detector_task = asyncio.create_task(start_device_detector())


# --------------------------------------------------------
# 공용 stop 함수 (main.py 내부 전용)
# --------------------------------------------------------
async def stop_device_detector_task():
    global device_detector_task

    async with detector_lock:
        if device_detector_task is None:
            logger.info("⏹ 중지 요청 → 이미 없음")
            return

        logger.info("⏸ Device Detector 중지 요청")
        device_detector_task.cancel()

        try:
            await device_detector_task
        except asyncio.CancelledError:
            logger.info("⛔ Device Detector 완전 종료됨")

        device_detector_task = None


# --------------------------------------------------------
# 서버 종료시 감지 루프 종료
# --------------------------------------------------------
@app.on_event("shutdown")
async def shutdown():
    await stop_device_detector_task()
    logger.info("🛑 서버 종료: Device Detector 종료 완료")


# --------------------------------------------------------
# analyze 요청: 반드시 비동기로 실행해야 함
# --------------------------------------------------------
@app.post("/analyze")
async def analyze(payload: dict):
    # run_anomaly_detection은 async 함수 → 반드시 await 필요
    result = await run_anomaly_detection()
    return result


# --------------------------------------------------------
# 수동 start API
# --------------------------------------------------------
@app.post("/device/start")
async def start_device():
    global device_detector_task

    async with detector_lock:
        if device_detector_task is not None and not device_detector_task.done():
            return {"status": "already_running"}

        logger.info("▶ Device Detector 수동 시작")
        device_detector_task = asyncio.create_task(start_device_detector())
        return {"status": "started"}


# --------------------------------------------------------
# 수동 stop API
# --------------------------------------------------------
@app.post("/device/stop")
async def stop_device():
    await stop_device_detector_task()
    return {"status": "stopped"}
