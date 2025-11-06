from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .websocket_manager import ConnectionManager

app = FastAPI()
manager = ConnectionManager()

class SttModeRequest(BaseModel):
    mode: str  # "buffered" 또는 "streaming"

class IntentDoneRequest(BaseModel):
    branch: str  # "AI_SUPPORTER" 또는 "OPERATOR"

@app.post("/api/stt/mode")
async def set_stt_mode(request: SttModeRequest):
    """
    STT 모드를 변경합니다.
    Android에서 Intent 분류 후 호출하면 됩니다.
    """
    manager.set_stt_mode(request.mode)
    
    # 스트리밍 모드로 전환 시 마이크를 활성화 (Intent 분류 중간에 OFF되었을 수 있음)
    if request.mode == "streaming":
        mic = manager.get_mic_stream()
        if mic and not mic.stream.is_active():
            mic.resume()
            print("🔊 마이크 ON (스트리밍 모드 전환)")
    
    return {"status": "ok", "mode": manager.get_stt_mode()}

@app.get("/api/stt/mode")
async def get_stt_mode():
    """현재 STT 모드를 조회합니다."""
    return {"mode": manager.get_stt_mode()}

@app.post("/api/stt/intent_done")
async def intent_done(request: IntentDoneRequest):
    """
    Intent 분류 완료 신호를 받습니다.
    Android에서 Intent 분류 완료 후 호출하면 됩니다.
    
    Args:
        branch: "AI_SUPPORTER" 또는 "OPERATOR"
    """
    if request.branch not in ["AI_SUPPORTER", "OPERATOR"]:
        raise HTTPException(status_code=400, detail="Invalid branch. Must be 'AI_SUPPORTER' or 'OPERATOR'")
    
    mic = manager.get_mic_stream()
    
    if request.branch == "OPERATOR":
        # OPERATOR 분기: 마이크를 즉시 활성화하여 대기 상태로 복귀
        if mic:
            if not mic.stream.is_active():
                mic.resume()
                print("🔊 마이크 ON (OPERATOR 분기 완료, 대기 상태로 복귀)")
            else:
                print("✅ 마이크 이미 활성 상태 (OPERATOR 분기 완료)")
        # STT 모드를 buffered로 유지 (다음 Wakeword 대기)
        manager.set_stt_mode("buffered")
        return {
            "status": "ok",
            "branch": request.branch,
            "message": "OPERATOR 분기 완료. 마이크 활성화하여 대기 상태로 복귀.",
            "stt_mode": manager.get_stt_mode()
        }
    
    elif request.branch == "AI_SUPPORTER":
        # AI_SUPPORTER 분기: 이미 스트리밍 모드로 전환되었을 것으로 예상
        # 모바일이 POST /api/stt/mode로 이미 전환했을 수 있음
        current_mode = manager.get_stt_mode()
        if current_mode != "streaming":
            # 아직 스트리밍 모드로 전환되지 않았다면 전환
            manager.set_stt_mode("streaming")
            print("✅ AI_SUPPORTER 분기 완료, 스트리밍 모드로 전환")
        
        # 마이크 활성화 (Intent 분류 중간에 OFF되었을 수 있음)
        if mic:
            if not mic.stream.is_active():
                mic.resume()
                print("🔊 마이크 ON (AI_SUPPORTER 분기 완료, 스트리밍 준비)")
            else:
                print("✅ 마이크 이미 활성 상태 (AI_SUPPORTER 분기 완료)")
        
        return {
            "status": "ok",
            "branch": request.branch,
            "message": "AI_SUPPORTER 분기 완료. 스트리밍 모드 준비 완료.",
            "stt_mode": manager.get_stt_mode()
        }
