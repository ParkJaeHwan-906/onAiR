# 📄 app/main.py
from fastapi import FastAPI
from app.routers import sensor, camera, control
from app.sockets.socket_manager import sio

app = FastAPI(
    title="Raspberry Pi FastAPI Server",
    root_path="/raspi"
)

# 라우터 등록
app.include_router(sensor.router)
app.include_router(camera.router)
app.include_router(control.router)


# ✅ 연결 / 해제 함수
def connect_to_socket():
    try:
        sio.connect("http://192.168.43.199:8000", socketio_path="/ws")
        print("✅ Connected manually to EC2 Socket Server")
    except Exception as e:
        print("⚠️ Connection failed:", e)

def disconnect_from_socket():
    sio.disconnect()


# ✅ FastAPI 이벤트 훅 등록
@app.on_event("startup")
def on_startup():
    print("🚀 FastAPI starting up...")
    connect_to_socket()

@app.on_event("shutdown")
def on_shutdown():
    print("🛑 FastAPI shutting down...")
    disconnect_from_socket()
