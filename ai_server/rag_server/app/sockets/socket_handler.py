# app/sockets/socket_handler.py
"""
FastAPI 서버용 Socket.IO 이벤트 핸들러

설계 요구사항:
1. 라즈베리파이로부터 STT 텍스트 직접 수신 (WebSocket)
2. 모바일과 Clarify 턴 주고받기 (WebSocket)
3. Streaming STT 처리
"""
import socketio
import cv2
import numpy as np
from typing import Dict, Any, Optional
from app.services.intent_service import classify_intent
from app.services import memory
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.answerability import comprehensive_evidence_check, normalize_query_style
from app.services.generator import llm_generate_answer
from app.services.tts_service import text_to_speech
from app.services.cv_service import run_cv_model
from app.services.llm_service import clarify_query

# Gemini 모델 import (clarify_qa_turn에서 사용)
try:
    import google.generativeai as genai
    from app.core.config import settings
    genai_available = True
    if settings.GMS_API_KEY:
        genai.configure(api_key=settings.GMS_API_KEY)
except Exception:
    genai = None
    genai_available = False

# Socket.IO 서버 인스턴스 (main.py에서 생성)
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
)

# 디바이스 타입 저장 (세션 ID → 디바이스 타입)
device_map: Dict[str, str] = {}  # { sid: "raspi" | "mobile" | "pc" }

# Clarify 세션 추적 (session_id → 현재 Clarify 턴 정보)
clarify_sessions: Dict[str, Dict[str, Any]] = {}  # { session_id: { turn_id, history, ... } }


def init_socketio():
    """Socket.IO 서버 인스턴스를 설정하고 이벤트 핸들러 등록"""
    if sio is None:
        print("❌ ERROR: sio 인스턴스가 None입니다!")
        return
    
    print(f"🔍 Socket.IO 서버 인스턴스 확인: {sio}")
    
    # 이벤트 핸들러 등록 (데코레이터 대신 직접 등록)
    sio.on("connect")(handle_connect)
    sio.on("disconnect")(handle_disconnect)
    sio.on("register_device")(handle_register_device)
    sio.on("stt_result")(handle_stt_result)
    sio.on("start_clarify_session")(handle_start_clarify_session)
    sio.on("end_clarify_session")(handle_end_clarify_session)
    sio.on("clarify_response")(handle_clarify_response)  # 모바일에서 오는 Clarify 응답 수신
    sio.on("clarify_input")(handle_clarify_input)  # 모바일에서 오는 Clarify 입력 수신 (Socket.IO를 통해)
    sio.on("control_raspi")(handle_control_raspi)  # 모바일에서 라즈베리파이 제어 명령
    sio.on("video_frame")(handle_video_frame)  
    
    print("✅ Socket.IO 이벤트 핸들러 등록 완료")


# === 타입별 브로드캐스트 (안전 버전) ===
async def broadcast_to(device_types, event: str, payload: dict):
    """
    특정 디바이스 타입(하나 또는 여러 개)에 이벤트 전송
    - device_types: 문자열('raspi') 또는 리스트(['raspi', 'mobile'])
    - payload: dict 형태의 전송 데이터
    """
    if isinstance(device_types, str):
        device_types = [device_types]

    # ✅ dictionary snapshot으로 안전한 iteration
    targets = list(device_map.items())
    sent_count = 0

    for sid, dev in targets:
        if dev in device_types:
            try:
                await sio.emit(event, payload, to=sid)
                sent_count += 1
            except Exception as e:
                # 연결 끊긴 클라이언트가 있을 수 있으므로 예외 무시하고 다음으로 진행
                print(f"⚠️ [broadcast_to] Failed to emit to {sid}: {e}")
                # 안전하게 제거 시도 (이미 끊겼을 수도 있음)
                try:
                    if sid in device_map:
                        del device_map[sid]
                except Exception:
                    pass


# ========================================
# 연결 이벤트
# ========================================

async def handle_connect(sid, environ):
    """클라이언트 연결"""
    try:
        print(f"✅ Client connected: {sid}")
        if sio:
            await sio.emit("server_message", {"msg": "Connected"}, to=sid)
        # 연결 허용 (명시적으로 True 반환하거나 아무것도 반환하지 않으면 허용)
        return True
    except Exception as e:
        print(f"❌ Connection error for {sid}: {e}")
        import traceback
        traceback.print_exc()
        # 예외 발생 시 연결 거부
        return False


async def handle_disconnect(sid):
    """클라이언트 연결 해제"""
    print(f"❌ Disconnected: {sid}")
    if sid in device_map:
        print(f"🧹 Removing device: {device_map[sid]}")
        del device_map[sid]


async def handle_register_device(sid, data):
    """디바이스 등록"""
    device = data.get("device", "unknown")
    device_map[sid] = device
    if sio:
        await sio.save_session(sid, {"device": device})
    
    print(f"🔗 Registered device: {device} ({sid})")
    if sio:
        await sio.emit("server_message", {"msg": f"Device '{device}' registered"}, to=sid)


# ========================================
# STT 이벤트 핸들러 (버퍼링 + Streaming)
# ========================================

async def handle_stt_result(sid, data):
    """
    라즈베리파이로부터 STT 결과 수신 (버퍼링 또는 Streaming)
    
    설계 요구사항:
    - 버퍼링 STT: type="final" → Gemini-Flash로 Intent 분류 → 모바일 전송
    - Streaming STT: type="interim" 또는 "final" → Redis 세션에 추가 → Clarify 처리
    """
    sender_device = device_map.get(sid, "unknown")
    
    # 라즈베리파이에서만 받음
    if sender_device != "raspi":
        print(f"⚠️ STT 결과는 라즈베리파이에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    stt_type = data.get("type", "unknown")
    stt_text = data.get("text", "").strip()
    confidence = data.get("confidence")
    session_id = data.get("session_id")  # Clarify 세션 ID (있는 경우)
    
    print(f"📝 STT 결과 수신 [raspi]: type={stt_type}, text={stt_text[:50]}...")
    
    # 버퍼링 STT (type="final"이고 session_id가 없음)
    if stt_type == "final" and not session_id:
        # 1. 먼저 모바일로 SSE 연결 시작 요청 전송
        try:
            await broadcast_to("mobile", "start_sse_connection", {
                "text": stt_text,
                "timestamp": None  # 필요시 추가
            })
            print(f"📡 모바일로 SSE 연결 시작 요청 전송: '{stt_text[:50]}...'")
        except Exception as e:
            print(f"⚠️ SSE 연결 시작 요청 전송 실패: {e}")
        
        # 2. Gemini-Flash로 Intent 분류 및 모바일로 전송
        try:
            intent_result = classify_intent(stt_text)
            intent = intent_result.get("intent", "AI_SUPPORTER")
            
            await broadcast_to("mobile", "intent_result", {
                "text": stt_text,
                "intent": intent,
                "confidence": intent_result.get("confidence", 0.5),
                "reasoning": intent_result.get("reasoning", ""),
                "stt_confidence": confidence  # STT 신뢰도
            })
            
            print(f"✅ 버퍼링 STT 처리 완료: '{stt_text[:50]}...' → Intent: {intent} (신뢰도: {intent_result.get('confidence', 0.5):.2f})")
            
            # AI_SUPPORTER 분기인 경우 CV 모델 실행
            if intent == "AI_SUPPORTER":
                try:
                    cv_result = await run_cv_model()
                    
                    if not cv_result.get("detected", False):
                        # CV 모델이 오류를 탐지하지 못한 경우
                        print(f"⚠️ CV 모델 오류 탐지 실패: {cv_result.get('message', '')}")
                        
                        # 모바일과 라즈베리파이로 cv_detection_failed 이벤트 전송
                        await broadcast_to("mobile", "cv_detection_failed", {
                            "message": "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다."
                        })
                        
                        await broadcast_to("raspi", "cv_detection_failed", {
                            "message": "오류를 탐지하지 못했습니다. Streaming STT 세션을 시작하세요."
                        })
                        
                        # 라즈베리파이에 마이크 켜고 Streaming STT 세션 시작 요청
                        # (라즈베리파이에서 이 이벤트를 받아서 처리)
                    else:
                        # CV 모델이 오류를 탐지한 경우
                        print(f"✅ CV 모델 오류 탐지 성공: {cv_result.get('error_type', 'Unknown')}")
                        # TODO: 오류 탐지 성공 시 처리 로직 추가
                        
                except Exception as e:
                    print(f"❌ CV 모델 실행 오류: {e}")
                    # CV 모델 오류 시에도 탐지 실패로 처리
                    await broadcast_to("mobile", "cv_detection_failed", {
                        "message": "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다."
                    })
                    await broadcast_to("raspi", "cv_detection_failed", {
                        "message": "오류를 탐지하지 못했습니다. Streaming STT 세션을 시작하세요."
                    })
                    
        except Exception as e:
            print(f"❌ 버퍼링 STT 처리 오류: {e}")
            # 에러 발생 시 기본값으로 AI_SUPPORTER 전송
            await broadcast_to("mobile", "intent_result", {
                "text": stt_text,
                "intent": "AI_SUPPORTER",
                "confidence": 0.5,
                "reasoning": f"Intent 분류 중 오류 발생: {e}",
                "stt_confidence": confidence
            })
    
    # Streaming STT (Clarify 루프 중)
    elif session_id:
        # Redis 세션에 STT 텍스트 추가
        memory.append_event(session_id, {
            "role": "user",
            "type": "streaming_stt",
            "data": {
                "text": stt_text,
                "type": stt_type,
                "confidence": confidence
            }
        })
        
        # type="final"이면 Clarify 처리 시작 (새로운 방식: clarify_qa_turn)
        if stt_type == "final":
            await process_clarify_qa_turn(session_id, stt_text)
        
        print(f"✅ Streaming STT 수신 [session={session_id}]: '{stt_text[:50]}...'")


# ========================================
# Clarify 루프 처리
# ========================================

async def process_clarify_turn(session_id: str, query: str, force_green: bool = False):
    """
    Clarify 턴 처리:
    1. Redis 히스토리 로드
    2. Hybrid Search + Rerank
    3. Evidence Check (RED/YELLOW/GREEN)
    4. RED/YELLOW → Clarify 질문 생성 (Gemini Flash)
    5. GREEN → 최종 답변 생성 (GPT-4o)
    6. 모바일로 WebSocket 이벤트 전송
    """
    # 히스토리 로드
    history = memory.get_history(session_id)
    history_context = ""
    
    # 최근 사용자 query 2개 결합
    user_lines = []
    for ev in reversed(history):
        if ev.get("role") == "user" and ev.get("type") in ["query", "streaming_stt"]:
            text = ev.get("data", {}).get("text", "") or ev.get("data", {}).get("query", "")
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
        from app.services.answerability import make_clarify_prompt
        
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
        
        # 모바일로 Clarify 턴 전송
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
        
        print(f"📤 Clarify 턴 {turn_id} 전송 [session={session_id}]: {gate_decision}")
    
    # GREEN → 최종 답변 생성
    else:
        snippets = [h["source"]["content"] for h in used_hits]
        answer_text = llm_generate_answer(effective_query, snippets)
        
        # TTS 생성
        try:
            tts_result = text_to_speech(answer_text)
            audio_url = None  # 또는 파일 저장 후 URL 생성
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
        
        # 모바일로 최종 답변 전송
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
        
        print(f"✅ 최종 답변 생성 완료 [session={session_id}]")


# ========================================
# 새로운 Clarify 루프 처리 (작업자 질문 + LLM 답변)
# ========================================

async def process_clarify_qa_turn(session_id: str, user_question: str):
    """
    Streaming STT 세션 중 Clarify 질문/답변 턴 처리:
    1. Gemini-Flash로 clarify 여부 판단 (need_clarify)
    2. 구체화 필요 시 소질문 생성 및 LLM 답변 생성
    3. TTS 변환 후 clarify_qa_turn 이벤트 전송
    4. 충분히 구체화되면 GPT-4o로 최종 답변 생성
    """
    # 히스토리 로드
    history = memory.get_history(session_id)
    
    # 세션 정보 가져오기 또는 생성
    if session_id not in clarify_sessions:
        clarify_sessions[session_id] = {
            "turns": [],
            "history": []
        }
    
    turn_id = len(clarify_sessions[session_id]["turns"]) + 1
    
    try:
        # 1. Gemini-Flash로 clarify 여부 판단
        clarify_result = clarify_query(user_question)
        need_clarify = not clarify_result.get("answerable", True)
        
        if need_clarify:
            # 구체화 필요: 소질문 생성 및 LLM 답변 생성
            clarify_question = clarify_result.get("clarify", "문제 상황을 구체적으로 말씀해주세요.")
            
            # LLM 답변 생성 (Gemini-Flash 사용)
            try:
                if genai_available:
                    model_qa = genai.GenerativeModel("gemini-1.5-flash")
                    
                    qa_prompt = f"""다음 질문에 대해 간단하고 명확하게 답변해주세요.

질문: {clarify_question}

답변은 1-2문장으로 간결하게 작성해주세요."""
                    
                    qa_response = model_qa.generate_content(qa_prompt)
                    llm_answer = qa_response.text.strip()
                else:
                    llm_answer = "문제 상황을 구체적으로 말씀해주시면 더 정확한 도움을 드릴 수 있습니다."
            except Exception as e:
                print(f"⚠️ LLM 답변 생성 실패: {e}")
                llm_answer = "문제 상황을 구체적으로 말씀해주시면 더 정확한 도움을 드릴 수 있습니다."
            
            # TTS 변환
            try:
                tts_result = text_to_speech(llm_answer)
                audio_content = tts_result.get("audio_content")
                audio_encoding = tts_result.get("mime_type")
            except Exception as e:
                print(f"⚠️ TTS 생성 실패: {e}")
                audio_content = None
                audio_encoding = None
            
            # clarify_qa_turn 이벤트 전송
            await broadcast_to("mobile", "clarify_qa_turn", {
                "session_id": session_id,
                "turn_id": turn_id,
                "user_question": user_question,
                "llm_answer": llm_answer,
                "audio_content": audio_content,
                "audio_encoding": audio_encoding,
                "need_clarify": True,
                "status": "success"
            })
            
            # 세션 정보 업데이트
            clarify_sessions[session_id]["turns"].append({
                "turn_id": turn_id,
                "user_question": user_question,
                "llm_answer": llm_answer,
                "need_clarify": True
            })
            
            print(f"📤 Clarify 질문/답변 턴 {turn_id} 전송 [session={session_id}]: need_clarify=True")
            
        else:
            # 충분히 구체화됨: GPT-4o로 최종 답변 생성
            # 히스토리 컨텍스트 구성
            history_context = ""
            user_lines = []
            for ev in reversed(history):
                if ev.get("role") == "user" and ev.get("type") == "streaming_stt":
                    text = ev.get("data", {}).get("text", "")
                    if text:
                        user_lines.append(text)
                    if len(user_lines) >= 3:  # 최근 3개 질문 사용
                        break
            
            if user_lines:
                history_context = " \n".join(reversed(user_lines))
            
            effective_query = f"{history_context} \n{user_question}" if history_context else user_question
            normalized_query = normalize_query_style(effective_query)
            
            # Hybrid Search + Rerank
            base_hits = hybrid_retrieve(normalized_query, top_k=8)
            hits = rerank(normalized_query, base_hits, top_k=6)
            used_hits = hits[:5]
            
            if not hits:
                await broadcast_to("mobile", "clarify_qa_turn", {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "user_question": user_question,
                    "llm_answer": "관련 문서를 찾을 수 없습니다.",
                    "audio_content": None,
                    "audio_encoding": None,
                    "need_clarify": False,
                    "status": "error"
                })
                return
            
            # 최종 답변 생성 (GPT-4o)
            snippets = [h["source"]["content"] for h in used_hits]
            answer_text = llm_generate_answer(effective_query, snippets)
            
            # TTS 생성
            try:
                tts_result = text_to_speech(answer_text)
                audio_content = tts_result.get("audio_content")
                audio_encoding = tts_result.get("mime_type")
            except Exception as e:
                print(f"⚠️ TTS 생성 실패: {e}")
                audio_content = None
                audio_encoding = None
            
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
            
            # 최종 답변 전송
            await broadcast_to("mobile", "final_answer", {
                "session_id": session_id,
                "turn_id": turn_id,
                "status": "completed",
                "answer": answer_text,
                "audio_content": audio_content,
                "audio_encoding": audio_encoding,
                "citations": [
                    {
                        "section": h["source"]["section"],
                        "pages": h["source"]["pages"],
                    }
                    for h in used_hits[:3]
                ]
            })
            
            print(f"✅ 최종 답변 생성 완료 [session={session_id}]")
            
    except Exception as e:
        print(f"❌ Clarify 질문/답변 턴 처리 오류: {e}")
        import traceback
        traceback.print_exc()
        
        await broadcast_to("mobile", "clarify_qa_turn", {
            "session_id": session_id,
            "turn_id": turn_id,
            "user_question": user_question,
            "llm_answer": "",
            "audio_content": None,
            "audio_encoding": None,
            "need_clarify": True,
            "status": "error"
        })


# ========================================
# Clarify 세션 시작/종료
# ========================================

async def handle_start_clarify_session(sid, data):
    """
    모바일에서 Clarify 세션 시작 요청
    """
    sender_device = device_map.get(sid, "unknown")
    
    if sender_device != "mobile":
        return
    
    session_id = data.get("session_id")
    if not session_id:
        await sio.emit("error", {"msg": "session_id가 필요합니다."}, to=sid)
        return
    
    clarify_sessions[session_id] = {
        "turns": [],
        "started_at": None
    }
    
    await sio.emit("clarify_session_started", {"session_id": session_id}, to=sid)
    print(f"✅ Clarify 세션 시작: {session_id}")


async def handle_end_clarify_session(sid, data):
    """
    모바일에서 Clarify 세션 종료 요청
    """
    sender_device = device_map.get(sid, "unknown")
    
    if sender_device != "mobile":
        return
    
    session_id = data.get("session_id")
    if session_id:
        memory.clear_history(session_id)
        clarify_sessions.pop(session_id, None)
        await sio.emit("clarify_session_ended", {"session_id": session_id}, to=sid)
        print(f"✅ Clarify 세션 종료: {session_id}")


async def handle_clarify_response(sid, data):
    """
    모바일에서 Clarify 질문에 대한 사용자 응답 수신
    
    모바일이 clarify_turn 이벤트를 받은 후 사용자가 응답을 입력하면
    이 이벤트로 전송됨.
    
    Args:
        data: {
            "session_id": "uuid",
            "turn_id": 1,
            "response": "사용자 응답 텍스트",
            "action": "continue" | "skip" | "cancel"
        }
    """
    sender_device = device_map.get(sid, "unknown")
    
    if sender_device != "mobile":
        print(f"⚠️ Clarify 응답은 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    session_id = data.get("session_id")
    turn_id = data.get("turn_id")
    response_text = data.get("response", "").strip()
    action = data.get("action", "continue")
    
    if not session_id:
        await sio.emit("error", {"msg": "session_id가 필요합니다."}, to=sid)
        return
    
    if action == "cancel":
        # 세션 취소
        memory.clear_history(session_id)
        clarify_sessions.pop(session_id, None)
        await sio.emit("clarify_session_cancelled", {"session_id": session_id}, to=sid)
        print(f"❌ Clarify 세션 취소: {session_id}")
        return
    
    if action == "skip":
        # 이 Clarify 턴 건너뛰기 (GREEN으로 강제 전환)
        # 히스토리에서 현재 쿼리만 사용하여 재처리
        history = memory.get_history(session_id)
        last_query = None
        for ev in reversed(history):
            if ev.get("role") == "user" and ev.get("type") == "streaming_stt":
                last_query = ev.get("data", {}).get("text", "")
                break
        
        if last_query:
            # 강제로 GREEN 처리하여 최종 답변 생성
            await process_clarify_turn(session_id, last_query, force_green=True)
        return
    
    # action == "continue": 사용자 응답을 Redis에 저장하고 다음 Clarify 턴 처리
    if response_text:
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
                if len(user_lines) >= 3:  # 최근 3개까지 결합
                    break
        
        if user_lines:
            history_context = " \n".join(reversed(user_lines))
        
        combined_query = f"{history_context}" if history_context else response_text
        
        # 재처리 (Clarify 턴 반복)
        await process_clarify_turn(session_id, combined_query)
        
        print(f"✅ Clarify 응답 수신 [session={session_id}, turn={turn_id}]: '{response_text[:50]}...'")
    else:
        await sio.emit("error", {"msg": "응답 텍스트가 비어있습니다."}, to=sid)

# ========================================
# Raspberry Pi 비디오 프레임 처리
# ========================================

@sio.on("video_frame")
async def handle_video_frame(sid, data):
    """라즈베리파이 → JPEG binary 수신 후 모션 추정"""
    sender_device = device_map.get(sid, "unknown")
    if not data:
        return

    np_data = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
    if frame is None:
        print("⚠️ Failed to decode frame")
        return

    # === 모션 계산 ===
    result = await motion_core.process_frame(frame, sid=sid)

    # === 결과 전송 ===
    if result["status"] == "ok":
        x, y, z = result["x"], result["y"], result["z"]
        print(f"📍 Camera position: x={x:.3f}, y={y:.3f}, z={z:.3f}")
        await broadcast_to("pc", "ar_marker", {"x": x, "y": y, "z": z})
    else:
        print(f"⚠️ Motion estimation status: {result['status']}")

    # === 프레임 브로드캐스트 (PC 디스플레이용) ===
    _, jpeg_bytes = cv2.imencode(".jpg", frame)
    await broadcast_to("pc", "video_frame", jpeg_bytes.tobytes())


# ========================================
# Clarify 입력 수신 (모바일 → FastAPI)
# ========================================

async def handle_clarify_input(sid, data):
    """
    모바일에서 전송된 Clarify 입력을 수신하여 처리
    clarify_response 핸들러를 호출하여 처리합니다.
    
    Args:
        sid: 클라이언트 세션 ID
        data: Clarify 입력 딕셔너리
            {
                "text": "사용자 입력 텍스트",
                "session_id": "세션 ID",
                "turn_id": 1 (optional),
                "action": "continue" | "skip" | "cancel" (optional)
            }
    """
    # clarify_response 핸들러로 위임
    await handle_clarify_response(sid, data)


# ========================================
# 라즈베리파이 제어 이벤트 (모바일 → 라즈베리파이)
# ========================================

async def handle_control_raspi(sid, data):
    """
    모바일에서 전송된 라즈베리파이 제어 명령을 수신하여 라즈베리파이로 전달
    
    Args:
        sid: 클라이언트 세션 ID
        data: 제어 명령 딕셔너리
            {
                "command": "start_streaming_stt" | "set_stt_mode" | "notify_intent_done",
                "mode": "buffered" | "streaming" (set_stt_mode일 때),
                "branch": "AI_SUPPORTER" | "OPERATOR" (notify_intent_done일 때)
            }
    """
    sender_device = device_map.get(sid, "unknown")
    
    # 모바일에서만 받음
    if sender_device != "mobile":
        print(f"⚠️ 라즈베리파이 제어 명령은 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    command = data.get("command", "")
    print(f"📡 라즈베리파이 제어 명령 수신 [mobile]: command={command}")
    
    # 라즈베리파이로 브로드캐스트
    await broadcast_to("raspi", "control_raspi", data)
    print(f"✅ 라즈베리파이 제어 명령 전달 완료: command={command}")