from fastapi import FastAPI
from routers import sensor, camera, control
from sockets.socket_manager import sio
import socketio

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
