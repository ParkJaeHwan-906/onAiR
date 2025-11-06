# app/routers/clarify_router.py
"""
Clarify 관련 HTTP 엔드포인트

socket_manager.py가 FastAPI를 호출하여 Clarify 처리를 수행합니다.
"""
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import logging
from app.services import memory
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.answerability import comprehensive_evidence_check, normalize_query_style, make_clarify_prompt
from app.services.generator import llm_generate_answer
from app.services.tts_service import text_to_speech
from app.utils.retry import retry_with_backoff

router = APIRouter(prefix="/api/clarify", tags=["Clarify"])
logger = logging.getLogger(__name__)

# Clarify 세션 추적 (session_id → 현재 Clarify 턴 정보)
clarify_sessions: Dict[str, Dict[str, Any]] = {}

# 처리 중인 세션 추적 (중복 처리 방지)
processing_sessions: set = set()


def get_socket_manager():
    """ai_ar의 socket_manager에서 broadcast_to 함수 가져오기 (재시도 로직 포함)"""
    import sys
    import os
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir))))
            ai_ar_path = os.path.join(project_root, "ai_ar")
            
            if os.path.exists(ai_ar_path) and ai_ar_path not in sys.path:
                sys.path.insert(0, ai_ar_path)
            
            from app.sockets.socket_manager import broadcast_to
            return broadcast_to
        except ImportError as e:
            if attempt < max_retries - 1:
                import time
                time.sleep(1)  # 1초 대기 후 재시도
                continue
            logger.error(f"⚠️ socket_manager를 찾을 수 없습니다 (시도 {attempt + 1}/{max_retries}): {e}")
            return None


class StreamingSTTRequest(BaseModel):
    session_id: str
    type: str  # "final" | "interim"
    text: str
    confidence: Optional[float] = None


class ClarifyProcessRequest(BaseModel):
    session_id: str
    query: str


class ClarifyResponseRequest(BaseModel):
    session_id: str
    turn_id: int
    response: str
    action: str = "continue"  # "continue" | "skip" | "cancel"


async def process_clarify_turn(session_id: str, query: str, force_green: bool = False):
    """
    Clarify 턴 처리 및 결과를 socket_manager로 브로드캐스트 (에러 핸들링 개선)
    """
    broadcast_to = get_socket_manager()
    if not broadcast_to:
        logger.error("❌ Socket.IO 서버에 연결할 수 없습니다.")
        # 에러 발생 시 모바일에게 알림
        try:
            # 재시도하여 broadcast_to 가져오기
            broadcast_to = get_socket_manager()
            if broadcast_to:
                await broadcast_to("mobile", "clarify_error", {
                    "session_id": session_id,
                    "message": "Socket.IO 서버 연결 실패"
                })
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="Socket.IO 서버에 연결할 수 없습니다.")
    
    # 히스토리 로드
    history = memory.get_history(session_id)
    history_context = ""
    
    # 최근 사용자 query 2개 결합
    user_lines = []
    for ev in reversed(history):
        if ev.get("role") == "user" and ev.get("type") in ["query", "streaming_stt", "clarify_response"]:
            text = ev.get("data", {}).get("text", "") or ev.get("data", {}).get("query", "") or ev.get("data", {}).get("response", "")
            if text:
                user_lines.append(text)
            if len(user_lines) >= 2:
                break
    
    if user_lines:
        history_context = " \n".join(reversed(user_lines))
    
    effective_query = f"{history_context} \n{query}" if history_context else query
    normalized_query = normalize_query_style(effective_query)
    
    # Hybrid Search + Rerank
    base_hits = hybrid_retrieve(normalized_query, top_k=8)
    hits = rerank(normalized_query, base_hits, top_k=6)
    used_hits = hits[:5]
    
    if not hits:
        await broadcast_to("mobile", "clarify_turn", {
            "session_id": session_id,
            "turn_id": len(clarify_sessions.get(session_id, {}).get("turns", [])) + 1,
            "status": "error",
            "message": "관련 문서를 찾을 수 없습니다."
        })
        return
    
    # Evidence Check
    need_clarify, evidence_stats = comprehensive_evidence_check(effective_query, used_hits)
    gate_decision = evidence_stats.get("gate_decision")
    
    # force_green=True면 강제로 GREEN 처리
    if force_green:
        gate_decision = "GREEN"
        need_clarify = False
        evidence_stats["gate_decision"] = "GREEN"
        evidence_stats["gate_rule"] = "FORCED_GREEN"
    
    # Clarify 세션 정보 업데이트
    if session_id not in clarify_sessions:
        clarify_sessions[session_id] = {
            "turns": [],
            "started_at": None
        }
    
    turn_id = len(clarify_sessions[session_id]["turns"]) + 1
    
    # RED/YELLOW → Clarify 질문 생성
    if need_clarify or gate_decision != "GREEN":
        clarified_result = make_clarify_prompt(effective_query, used_hits, evidence_stats)
        
        # Redis에 저장
        memory.append_event(session_id, {
            "role": "system",
            "type": "clarify",
            "data": {
                "turn_id": turn_id,
                "gate_decision": gate_decision,
                "clarify_guidance": clarified_result.get("guide", ""),
                "evidence_stats": evidence_stats
            }
        })
        
        clarify_sessions[session_id]["turns"].append({
            "turn_id": turn_id,
            "status": "clarify",
            "gate_decision": gate_decision
        })
        
        # 모바일로 Clarify 턴 전송 (에러 핸들링)
        try:
            await broadcast_to("mobile", "clarify_turn", {
                "session_id": session_id,
                "turn_id": turn_id,
                "status": "clarify",
                "gate_decision": gate_decision,
                "question": clarified_result.get("guide", ""),
                "examples": clarified_result.get("examples", []),
                "evidence_trace": evidence_stats.get("evidence_trace", {}),
                "missing_info": evidence_stats.get("missing_info", [])
            })
            logger.info(f"📤 Clarify 턴 {turn_id} 전송 [session={session_id}]: {gate_decision}")
        except Exception as e:
            logger.error(f"❌ Clarify 턴 전송 실패: {e}")
            # 재시도
            try:
                await retry_with_backoff(
                    broadcast_to,
                    max_attempts=2,
                    initial_delay=0.5,
                    exceptions=(Exception,),
                    device_types="mobile",
                    event="clarify_turn",
                    payload={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "status": "clarify",
                        "gate_decision": gate_decision,
                        "question": clarified_result.get("guide", ""),
                        "examples": clarified_result.get("examples", []),
                        "evidence_trace": evidence_stats.get("evidence_trace", {}),
                        "missing_info": evidence_stats.get("missing_info", [])
                    }
                )
            except Exception as retry_error:
                logger.error(f"❌ Clarify 턴 전송 재시도 실패: {retry_error}")
        
        print(f"📤 Clarify 턴 {turn_id} 전송 [session={session_id}]: {gate_decision}")
    
    # GREEN → 최종 답변 생성
    else:
        snippets = [h["source"]["content"] for h in used_hits]
        answer_text = llm_generate_answer(effective_query, snippets)
        
        # TTS 생성
        try:
            tts_result = text_to_speech(answer_text)
        except Exception as e:
            print(f"⚠️ TTS 생성 실패: {e}")
            tts_result = None
        
        # Redis에 저장
        memory.append_event(session_id, {
            "role": "assistant",
            "type": "final_answer",
            "data": {
                "answer": answer_text,
                "citations": [
                    {
                        "section": h["source"]["section"],
                        "pages": h["source"]["pages"],
                    }
                    for h in used_hits[:3]
                ]
            }
        })
        
        # 세션 초기화
        memory.clear_history(session_id)
        clarify_sessions.pop(session_id, None)
        
        # 모바일로 최종 답변 전송 (에러 핸들링)
        try:
            await broadcast_to("mobile", "final_answer", {
                "session_id": session_id,
                "turn_id": turn_id,
                "status": "completed",
                "answer": answer_text,
                "audio_content": tts_result.get("audio_content") if tts_result else None,
                "audio_encoding": tts_result.get("audio_encoding") if tts_result else None,
                "citations": [
                    {
                        "section": h["source"]["section"],
                        "pages": h["source"]["pages"],
                    }
                    for h in used_hits[:3]
                ]
            })
            
            # 🆕 라즈베리파이로 Streaming STT 종료 신호 전송
            try:
                await broadcast_to("raspi", "stop_streaming_stt", {
                    "session_id": session_id,
                    "reason": "final_answer_completed"
                })
                logger.info(f"🛑 Streaming STT 종료 신호 전송: session_id={session_id}")
            except Exception as e:
                logger.error(f"❌ Streaming STT 종료 신호 전송 실패: {e}")
            
            logger.info(f"✅ 최종 답변 생성 완료 [session={session_id}]")
        except Exception as e:
            logger.error(f"❌ 최종 답변 전송 실패: {e}")
            # 재시도
            try:
                await retry_with_backoff(
                    broadcast_to,
                    max_attempts=2,
                    initial_delay=0.5,
                    exceptions=(Exception,),
                    device_types="mobile",
                    event="final_answer",
                    payload={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "status": "completed",
                        "answer": answer_text,
                        "audio_content": tts_result.get("audio_content") if tts_result else None,
                        "audio_encoding": tts_result.get("audio_encoding") if tts_result else None,
                        "citations": [
                            {
                                "section": h["source"]["section"],
                                "pages": h["source"]["pages"],
                            }
                            for h in used_hits[:3]
                        ]
                    }
                )
            except Exception as retry_error:
                logger.error(f"❌ 최종 답변 전송 재시도 실패: {retry_error}")
        
        print(f"✅ 최종 답변 생성 완료 [session={session_id}]")


@router.post("/streaming")
async def handle_streaming_stt(request: StreamingSTTRequest = Body(...)):
    """
    Streaming STT 결과 수신 및 처리 (비동기 Task로 분리)
    
    socket_manager의 handle_stt_result에서 호출됩니다.
    """
    session_id = request.session_id
    stt_type = request.type
    stt_text = request.text.strip()
    
    if not stt_text:
        raise HTTPException(status_code=400, detail="텍스트가 비어있습니다.")
    
    # Redis 세션에 STT 텍스트 추가 (동기 처리, 빠름)
    memory.append_event(session_id, {
        "role": "user",
        "type": "streaming_stt",
        "data": {
            "text": stt_text,
            "type": stt_type,
            "confidence": request.confidence
        }
    })
    
    # type="final"이면 Clarify 처리 시작 (비동기 Task로 분리)
    if stt_type == "final":
        # 중복 처리 방지
        if session_id in processing_sessions:
            return {"success": True, "message": "이미 처리 중인 세션입니다."}
        
        processing_sessions.add(session_id)
        
        # 비동기 Task로 실행 (STT 수신을 블로킹하지 않음)
        asyncio.create_task(
            process_clarify_turn_async(session_id, stt_text)
        )
        
        return {"success": True, "message": f"Clarify 처리 시작: '{stt_text[:50]}...'"}
    
    return {"success": True, "message": f"Streaming STT 수신 완료: '{stt_text[:50]}...'"}


async def process_clarify_turn_async(session_id: str, query: str):
    """
    Clarify 턴 처리 (비동기 Task로 실행)
    """
    try:
        await process_clarify_turn(session_id, query)
    except Exception as e:
        logger.error(f"❌ Clarify 처리 오류 [session={session_id}]: {e}")
        # 에러 발생 시 모바일에게 알림
        broadcast_to = get_socket_manager()
        if broadcast_to:
            try:
                await broadcast_to("mobile", "clarify_error", {
                    "session_id": session_id,
                    "message": f"Clarify 처리 중 오류 발생: {str(e)}"
                })
            except Exception:
                pass
    finally:
        # 처리 완료 후 세션 제거
        processing_sessions.discard(session_id)


@router.post("/process")
async def handle_clarify_process(request: ClarifyProcessRequest = Body(...)):
    """
    Clarify 처리 요청
    
    명시적으로 Clarify 처리를 요청할 때 사용됩니다.
    """
    await process_clarify_turn(request.session_id, request.query)
    return {"success": True, "message": "Clarify 처리 완료"}


@router.post("/response")
async def handle_clarify_response(request: ClarifyResponseRequest = Body(...)):
    """
    모바일에서 Clarify 질문에 대한 사용자 응답 수신
    
    socket_manager의 clarify_response 이벤트 핸들러에서 호출됩니다.
    """
    session_id = request.session_id
    turn_id = request.turn_id
    response_text = request.response.strip()
    action = request.action
    
    if action == "cancel":
        memory.clear_history(session_id)
        clarify_sessions.pop(session_id, None)
        broadcast_to = get_socket_manager()
        if broadcast_to:
            await broadcast_to("mobile", "clarify_session_cancelled", {"session_id": session_id})
        return {"success": True, "message": "세션 취소됨"}
    
    if action == "skip":
        history = memory.get_history(session_id)
        last_query = None
        for ev in reversed(history):
            if ev.get("role") == "user" and ev.get("type") == "streaming_stt":
                last_query = ev.get("data", {}).get("text", "")
                break
        
        if last_query:
            await process_clarify_turn(session_id, last_query, force_green=True)
        return {"success": True, "message": "Clarify 턴 건너뛰기 완료"}
    
    # action == "continue"
    if not response_text:
        raise HTTPException(status_code=400, detail="응답 텍스트가 비어있습니다.")
    
    memory.append_event(session_id, {
        "role": "user",
        "type": "clarify_response",
        "data": {
            "turn_id": turn_id,
            "response": response_text,
            "action": action
        }
    })
    
    # 사용자 응답을 히스토리와 결합하여 재처리
    history = memory.get_history(session_id)
    history_context = ""
    
    user_lines = []
    for ev in reversed(history):
        if ev.get("role") == "user" and ev.get("type") in ["query", "streaming_stt", "clarify_response"]:
            text = ev.get("data", {}).get("text", "") or ev.get("data", {}).get("query", "") or ev.get("data", {}).get("response", "")
            if text:
                user_lines.append(text)
            if len(user_lines) >= 3:
                break
    
    if user_lines:
        history_context = " \n".join(reversed(user_lines))
    
    combined_query = f"{history_context}" if history_context else response_text
    
    # 재처리 (Clarify 턴 반복)
    await process_clarify_turn(session_id, combined_query)
    
    return {"success": True, "message": f"Clarify 응답 처리 완료: '{response_text[:50]}...'"}

