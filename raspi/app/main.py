from fastapi import FastAPI
from app.routers import sensor, camera, control
from app.sockets.socket_manager import sio
import socketio

import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

app = FastAPI(
    title="Raspberry Pi FastAPI Server",
    root_path="/raspi"
    )

# 라우터 등록
app.include_router(sensor.router)
app.include_router(camera.router)
app.include_router(control.router)

# Socket.io
asgi_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path="raspi/ws"
)

@app.get("/")
def root():
    return {"message": "FastAPI is running on Raspberry Pi Zero 2W!"}
