import socketio
from fastapi import FastAPI
from app.sockets.socket_manager import sio

# FastAPI 인스턴스 생성
app = FastAPI(
    title="AI_AR FastAPI Server",
    description="Fast API Server",
    version="1.0.0"
)

# Health Check 라우트
@app.get("/")
def read_root():
    return {"message": "Fast API Server is Running"}

# Socket.io 설정
asgi_app = socketio.ASGIApp(
    sio,                   
    other_asgi_app=app,     
    socketio_path="/ws"     
)
