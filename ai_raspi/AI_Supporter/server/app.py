"""
라즈베리파이 ConnectionManager 모듈

모든 통신은 Socket.IO를 통해 이루어지며, HTTP 서버는 사용하지 않습니다.
ConnectionManager는 Socket.IO 클라이언트와 STT 인스턴스를 관리합니다.
"""
from .websocket_manager import ConnectionManager

# ConnectionManager 인스턴스 생성 (Socket.IO 통신 관리용)
# 모든 통신은 Socket.IO를 통해 FastAPI 서버로 전송됩니다.
manager = ConnectionManager()

# ========================================
# 레거시: FastAPI HTTP 엔드포인트 (사용 안 함)
# ========================================
# 
# 이전에는 HTTP POST /api/stt/mode, /api/stt/intent_done 엔드포인트를 제공했지만,
# 현재는 모든 제어 명령이 Socket.IO를 통해 전달됩니다.
# 
# 레거시 코드 (참고용, 필요 시 활성화 가능):
# 
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# 
# app = FastAPI()
# 
# class SttModeRequest(BaseModel):
#     mode: str  # "buffered" 또는 "streaming"
# 
# class IntentDoneRequest(BaseModel):
#     branch: str  # "AI_SUPPORTER" 또는 "OPERATOR"
# 
# @app.post("/api/stt/mode")
# async def set_stt_mode(request: SttModeRequest):
#     manager.set_stt_mode(request.mode)
#     if request.mode == "streaming":
#         mic = manager.get_mic_stream()
#         if mic and not mic.stream.is_active():
#             mic.resume()
#     return {"status": "ok", "mode": manager.get_stt_mode()}
# 
# @app.post("/api/stt/intent_done")
# async def intent_done(request: IntentDoneRequest):
#     # ... (레거시 코드)
