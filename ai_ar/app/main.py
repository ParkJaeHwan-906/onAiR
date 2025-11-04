import socketio
from fastapi import FastAPI
from app.sockets.socket_manager import sio
from app.ar import video_handle   
from app.routers import status    

# FastAPI 인스턴스 생성
app = FastAPI(
    title="AI_AR FastAPI Server",
    description="Fast API Server with Socket.IO",
    version="1.0.0"
)

# REST 라우터 등록
app.include_router(status.router)

@app.get("/")
def read_root():
    return {"message": "ok"}

# Socket.IO 통합
asgi_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path="/ws"
)
