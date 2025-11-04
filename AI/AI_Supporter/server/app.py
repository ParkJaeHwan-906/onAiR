from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .websocket_manager import ConnectionManager

app = FastAPI()
manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
