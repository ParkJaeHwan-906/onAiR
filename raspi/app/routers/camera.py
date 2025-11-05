from fastapi import APIRouter
from app.sockets.socket_manager import sio
from app.services import camera_service

router = APIRouter(prefix="/camera", tags=["Camera"])

@router.post("/start_stream")
async def start_stream():
    def emit_frame(b64):
        # 프레임을 Socket.IO로 실시간 전송
        sio.start_background_task(sio.emit, "video-frame", {"frame": b64})
    camera_service.start_stream(emit_frame)
    return {"status": "streaming"}

@router.post("/stop_stream")
async def stop_stream():
    return camera_service.stop_stream()
