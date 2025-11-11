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
import asyncio
import os
import time
from typing import Dict, Any, Optional
from app.services.intent_service import classify_intent
from app.services import memory
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.answerability import comprehensive_evidence_check, normalize_query_style
from app.services.generator import llm_generate_answer
from app.services.tts_service import text_to_speech
from app.services.cv_service import run_cv_model
from app.services.llm_service import clarify_query
from app.ar import motion_core

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
    cors_allowed_origins='*',  # 모든 Origin 허용
    logger=False,  # 로거 비활성화
)

# 디바이스 타입 저장 (세션 ID → 디바이스 타입)
device_map: Dict[str, str] = {}  # { sid: "raspi" | "mobile" | "pc" }

# Clarify 세션 추적 (session_id → 현재 Clarify 턴 정보)
clarify_sessions: Dict[str, Dict[str, Any]] = {}  # { session_id: { turn_id, history, ... } }


# ========================================
# 🐛 단계별 수동 실행 모드 (디버깅용)
# ========================================

async def wait_for_next_step(step_name: str, step_number: str = ""):
    """
    단계별 수동 실행 모드: 다음 단계로 진행하기 전 대기
    
    Args:
        step_name: 현재 단계 이름 (로그 출력용)
        step_number: 단계 번호 (예: "6", "7", "12-1")
    
    사용법:
        - DEBUG_STEP_BY_STEP=True일 때: /tmp/next_step 파일이 생성될 때까지 대기
        - DEBUG_STEP_BY_STEP=False일 때: 바로 진행 (0.5초 딜레이만)
    """
    if not settings.DEBUG_STEP_BY_STEP:
        # 자동 모드: 짧은 딜레이만
        await asyncio.sleep(0.5)
        return
    
    # 수동 모드: 파일 트리거 대기
    trigger_file = settings.DEBUG_STEP_TRIGGER_FILE
    timeout = settings.DEBUG_STEP_WAIT_TIMEOUT
    
    print("=" * 80)
    print(f"⏸️  [단계 {step_number}] {step_name} 완료")
    print(f"   다음 단계로 진행하려면 다음 명령을 실행하세요:")
    print(f"   $ touch {trigger_file}")
    print(f"   또는 자동으로 진행하려면: $ echo 'auto' > {trigger_file}")
    print(f"   (최대 {timeout}초 대기)")
    print("=" * 80)
    
    # 기존 트리거 파일 삭제 (이전 단계에서 남아있을 수 있음)
    if os.path.exists(trigger_file):
        try:
            os.remove(trigger_file)
        except:
            pass
    
    # 파일이 생성될 때까지 대기
    start_time = time.time()
    check_interval = 0.5  # 0.5초마다 확인
    
    while True:
        if os.path.exists(trigger_file):
            # 파일 내용 확인 (auto 모드 체크)
            try:
                with open(trigger_file, 'r') as f:
                    content = f.read().strip()
                if content == "auto":
                    # 자동 모드: 이후 단계도 자동 진행
                    print(f"✅ 자동 모드 활성화 - 이후 단계는 자동 진행됩니다")
                    os.remove(trigger_file)
                    return
            except:
                pass
            
            # 수동 모드: 파일 삭제 후 진행
            try:
                os.remove(trigger_file)
            except:
                pass
            print(f"✅ 다음 단계 진행: {step_name}")
            print("=" * 80)
            await asyncio.sleep(0.2)  # 파일 삭제 후 짧은 딜레이
            return
        
        # 타임아웃 체크
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            print(f"⚠️ 타임아웃 ({timeout}초) - 자동으로 다음 단계 진행")
            print("=" * 80)
            return
        
        await asyncio.sleep(check_interval)


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
    sio.on("wakeword_detected")(handle_wakeword_detected)  # 라즈베리파이에서 Wakeword 감지 이벤트 수신
    sio.on("wakeword_audio_completed")(handle_wakeword_audio_completed)  # 모바일에서 음성 파일 재생 완료 이벤트 수신
    sio.on("start_clarify_session")(handle_start_clarify_session)
    sio.on("end_clarify_session")(handle_end_clarify_session)
    sio.on("clarify_response")(handle_clarify_response)  # 모바일에서 오는 Clarify 응답 수신
    sio.on("clarify_input")(handle_clarify_input)  # 모바일에서 오는 Clarify 입력 수신 (Socket.IO를 통해)
    sio.on("control_raspi")(handle_control_raspi)  # 모바일에서 라즈베리파이 제어 명령
    sio.on("video_frame")(handle_video_frame)  
    sio.on("ar-marker")(handle_ar_marker)
    
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
    
    # 디버깅: 현재 device_map 상태 출력
    # print(f"🔍 [broadcast_to] 디버깅: 요청 디바이스={device_types}, 이벤트={event}")
    # print(f"   현재 device_map: {dict(device_map)}")
    # print(f"   현재 연결된 디바이스 타입: {list(set(device_map.values()))}")
    
    # 연결된 디바이스 확인
    available_devices = [dev for sid, dev in targets if dev in device_types]
    if not available_devices:
        # print(f"⚠️ [broadcast_to] 연결된 디바이스가 없습니다. 요청: {device_types}, 현재 연결: {list(set(device_map.values()))}")
        # print(f"   device_map 상세: {[(sid[:10] + '...', dev) for sid, dev in targets]}")
        return

    # print(f"✅ [broadcast_to] 찾은 디바이스: {available_devices}")
    
    for sid, dev in targets:
        if dev in device_types:
            try:
                # print(f"📤 [broadcast_to] 이벤트 전송 시도: {event} → {dev} (sid={sid[:15]}...)")
                # print(f"   Payload: {str(payload)[:100]}...")
                await sio.emit(event, payload, to=sid)
                sent_count += 1
                # print(f"✅ [broadcast_to] 이벤트 전송 성공: {event} → {dev} (sid={sid[:15]}...)")
            except Exception as e:
                # 연결 끊긴 클라이언트가 있을 수 있으므로 예외 무시하고 다음으로 진행
                # print(f"⚠️ [broadcast_to] Failed to emit to {sid}: {e}")
                import traceback
                traceback.print_exc()
                # 안전하게 제거 시도 (이미 끊겼을 수도 있음)
                try:
                    if sid in device_map:
                        del device_map[sid]
                        # print(f"🧹 [broadcast_to] 디바이스 제거: {dev} (sid={sid[:15]}...)")
                except Exception:
                    pass
    
    # if sent_count == 0:
    #     print(f"⚠️ [broadcast_to] 이벤트 전송 실패: {event} → {device_types} (연결된 디바이스 없음)")
    # else:
    #     print(f"✅ [broadcast_to] 총 {sent_count}개 디바이스에 이벤트 전송 완료: {event} → {device_types}")


# ========================================
# 연결 이벤트
# ========================================

async def handle_connect(sid, environ):
    """클라이언트 연결"""
    try:
        # 클라이언트 정보 확인
        user_agent = environ.get("HTTP_USER_AGENT", "unknown")
        remote_addr = environ.get("REMOTE_ADDR", "unknown")
        print(f"✅ Client connected: {sid} (from {remote_addr}, user_agent={user_agent[:50]}...)")
        
        if sio:
            await sio.emit("server_message", {"msg": "Connected"}, to=sid)
        # 연결 허용 (명시적으로 True 반환하거나 아무것도 반환하지 않으면 허용)
        print(f"🔍 [DEBUG] handle_connect 성공, 연결 허용")
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
    
    # print("=" * 60)
    # print(f"🔗 [디바이스 등록] Registered device: {device} ({sid[:15]}...)")
    # print(f"📊 현재 연결된 디바이스: {list(device_map.values())} (총 {len(device_map)}개)")
    # print(f"   device_map 상세: {[(k[:15] + '...', v) for k, v in device_map.items()]}")
    # print("=" * 60)
    
    if sio:
        await sio.emit("server_message", {"msg": f"Device '{device}' registered"}, to=sid)


# ========================================
# Wakeword 이벤트 핸들러
# ========================================

async def handle_wakeword_detected(sid, data):
    """
    라즈베리파이로부터 Wakeword 감지 이벤트 수신
    모바일로 이벤트를 전송하여 음성 파일 재생 시작
    """
    sender_device = device_map.get(sid, "unknown")
    
    # 라즈베리파이에서만 받음
    if sender_device != "raspi":
        print(f"⚠️ Wakeword 감지 이벤트는 라즈베리파이에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    print("=" * 60)
    print(f"📝 [단계 2-1] FastAPI 서버: Wakeword 감지 이벤트 수신 [raspi]")
    print("=" * 60)
    await wait_for_next_step("Wakeword 감지 이벤트 수신 완료", "2-1")
    
    # 모바일로 Wakeword 감지 이벤트 전송 (음성 파일 재생 시작)
    print("=" * 60)
    print("📡 [단계 2-1-1] 모바일로 Wakeword 감지 이벤트 전송 (음성 파일 재생 시작)")
    print("=" * 60)
    await broadcast_to("mobile", "wakeword_detected", {
        "timestamp": None  # 필요시 추가
    })
    print("=" * 60)
    print("✅ [단계 2-1-1 완료] 모바일로 Wakeword 감지 이벤트 전송 완료")
    print("=" * 60)
    await wait_for_next_step("모바일로 Wakeword 감지 이벤트 전송 완료", "2-1-1")


async def handle_wakeword_audio_completed(sid, data):
    """
    모바일로부터 음성 파일 재생 완료 이벤트 수신
    라즈베리파이로 이벤트를 전송하여 버퍼링 STT 세션 시작
    """
    sender_device = device_map.get(sid, "unknown")
    
    # 모바일에서만 받음
    if sender_device != "mobile":
        print(f"⚠️ 음성 파일 재생 완료 이벤트는 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    print("=" * 60)
    print(f"📝 [단계 2-2] FastAPI 서버: 모바일 음성 파일 재생 완료 이벤트 수신 [mobile]")
    print("=" * 60)
    await wait_for_next_step("모바일 음성 파일 재생 완료 이벤트 수신 완료", "2-2")
    
    # 라즈베리파이로 음성 파일 재생 완료 이벤트 전송 (버퍼링 STT 세션 시작)
    print("=" * 60)
    print("📡 [단계 2-2-1] 라즈베리파이로 음성 파일 재생 완료 이벤트 전송 (버퍼링 STT 세션 시작)")
    print("=" * 60)
    await broadcast_to("raspi", "wakeword_audio_completed", {
        "timestamp": None  # 필요시 추가
    })
    print("=" * 60)
    print("✅ [단계 2-2-1 완료] 라즈베리파이로 음성 파일 재생 완료 이벤트 전송 완료")
    print("=" * 60)
    await wait_for_next_step("라즈베리파이로 음성 파일 재생 완료 이벤트 전송 완료", "2-2-1")


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
    
    print("=" * 60)
    print(f"📝 [단계 6] FastAPI 서버: STT 결과 수신 [raspi]")
    print(f"   타입: {stt_type}, 텍스트: {stt_text[:50]}...")
    print("=" * 60)
    await wait_for_next_step("STT 결과 수신 완료", "6")
    
    # 버퍼링 STT (type="final"이고 session_id가 없음)
    if stt_type == "final" and not session_id:
        # 1. 먼저 모바일로 SSE 연결 시작 요청 전송
        try:
            print("=" * 60)
            print("📡 [단계 6-1] 모바일로 SSE 연결 시작 요청 전송")
            print("=" * 60)
            await broadcast_to("mobile", "start_sse_connection", {
                "text": stt_text,
                "timestamp": None  # 필요시 추가
            })
            print(f"✅ 모바일로 SSE 연결 시작 요청 전송 완료: '{stt_text[:50]}...'")
            await wait_for_next_step("SSE 연결 시작 요청 전송 완료", "6-1")
        except Exception as e:
            print(f"⚠️ SSE 연결 시작 요청 전송 실패: {e}")
        
        # 2. Gemini-Flash로 Intent 분류 및 모바일로 전송
        try:
            print("=" * 60)
            print("🤖 [단계 7] Gemini-Flash로 Intent 분류 시작")
            print(f"   입력 텍스트: {stt_text[:50]}...")
            print("=" * 60)
            
            intent_result = classify_intent(stt_text)
            intent = intent_result.get("intent", "AI_SUPPORTER")
            
            print("=" * 60)
            print(f"✅ [단계 7 완료] Intent 분류 완료: {intent} (신뢰도: {intent_result.get('confidence', 0.5):.2f})")
            print("=" * 60)
            await wait_for_next_step("Intent 분류 완료", "7")
            
            # 모바일로 Intent 결과 전송
            print("=" * 60)
            print(f"📤 [단계 8] 모바일로 intent_result 이벤트 전송 시작")
            print(f"   Intent: {intent}, Text: '{stt_text[:50]}...'")
            print("=" * 60)
            
            await broadcast_to("mobile", "intent_result", {
                "text": stt_text,
                "intent": intent,
                "confidence": intent_result.get("confidence", 0.5),
                "reasoning": intent_result.get("reasoning", ""),
                "stt_confidence": confidence  # STT 신뢰도
            })
            
            print("=" * 60)
            print(f"✅ [단계 8 완료] 모바일로 intent_result 이벤트 전송 완료")
            print(f"   버퍼링 STT 처리 완료: '{stt_text[:50]}...' → Intent: {intent}")
            print("=" * 60)
            await wait_for_next_step("모바일로 intent_result 이벤트 전송 완료", "8")
            
            # AI_SUPPORTER 분기인 경우 모바일에서 음성 파일 재생 완료 대기 후 CV 모델 실행
            if intent == "AI_SUPPORTER":
                # 모바일에서 음성 파일 재생 완료 대기 (최대 10초)
                # 주의: 모바일에서 음성 파일 재생 완료 이벤트를 별도로 전송하지 않으므로,
                # 음성 파일 길이를 고려하여 대기 시간 설정
                print("=" * 60)
                print("⏳ [단계 8-1] 모바일 AI_SUPPORTER 음성 파일 재생 완료 대기 중...")
                print("   💡 모바일에서 'AI_Supporter 기능을 시작합니다. 오류 탐지.' 재생 중...")
                print("=" * 60)
                await asyncio.sleep(5)  # 음성 파일 재생 시간 대기 (약 5초)
                print("=" * 60)
                print("✅ [단계 8-1 완료] 모바일 AI_SUPPORTER 음성 파일 재생 완료 대기 종료")
                print("=" * 60)
                await wait_for_next_step("모바일 AI_SUPPORTER 음성 파일 재생 완료 대기", "8-1")
                
                # CV 모델 실행
                try:
                    print("=" * 60)
                    print("🔍 [단계 9] CV 모델 실행 시작")
                    print("=" * 60)
                    print("⚠️ CV 모델 연결은 아직 구현되지 않았습니다. 비워둡니다.")
                    print("=" * 60)
                    await wait_for_next_step("CV 모델 실행 (비워둠)", "9")
                    
                    cv_result = await run_cv_model()
                    
                    if not cv_result.get("detected", False):
                        # CV 모델이 오류를 탐지하지 못한 경우
                        print("=" * 60)
                        print(f"⚠️ [단계 9 완료] CV 모델 오류 탐지 실패: {cv_result.get('message', '')}")
                        print("=" * 60)
                        await wait_for_next_step("CV 모델 실행 완료 (탐지 실패)", "9")
                        
                        # 모바일과 라즈베리파이로 cv_detection_failed 이벤트 전송
                        print("=" * 60)
                        print("📤 [단계 10] 모바일로 cv_detection_failed 이벤트 전송 시작")
                        print("=" * 60)
                        await broadcast_to("mobile", "cv_detection_failed", {
                            "message": "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다."
                        })
                        print("✅ [단계 10 완료] 모바일로 cv_detection_failed 이벤트 전송 완료")
                        await wait_for_next_step("모바일로 cv_detection_failed 이벤트 전송 완료", "10")
                        
                        print("=" * 60)
                        print("📤 [단계 11] 라즈베리파이로 cv_detection_failed 이벤트 전송 시작")
                        print("=" * 60)
                        await broadcast_to("raspi", "cv_detection_failed", {
                            "message": "오류를 탐지하지 못했습니다. Streaming STT 세션을 시작하세요."
                        })
                        print("✅ [단계 11 완료] 라즈베리파이로 cv_detection_failed 이벤트 전송 완료")
                        print("=" * 60)
                        await wait_for_next_step("라즈베리파이로 cv_detection_failed 이벤트 전송 완료", "11")
                        
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
            print("=" * 60)
            print(f"📝 [단계 13] FastAPI 서버: Streaming STT 결과 수신 [raspi]")
            print(f"   Session ID: {session_id}")
            print(f"   타입: {stt_type}, 텍스트: {stt_text[:50]}...")
            print("=" * 60)
            await wait_for_next_step("Streaming STT 결과 수신 완료", "13")
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
        answer_result = llm_generate_answer(effective_query, snippets, used_hits)
        
        # 구조화된 답변에서 TTS 텍스트 추출
        answer_text = answer_result.get("tts_text") or answer_result.get("summary") or answer_result.get("answer", "")
        structured_answer = answer_result  # 전체 구조화된 답변
        
        # TTS 생성 (TTS 친화적 텍스트 사용)
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
        
        # 모바일로 최종 답변 전송 (구조화된 답변 포함)
        await broadcast_to("mobile", "final_answer", {
            "session_id": session_id,
            "turn_id": turn_id,
            "status": "completed",
            "answer": answer_text,  # TTS 친화적 텍스트
            "structured_answer": structured_answer,  # 전체 구조화된 답변 (UI 표시용)
            "audio_content": tts_result.get("audio_content") if tts_result else None,
            "audio_encoding": tts_result.get("audio_encoding") if tts_result else None,
            "citations": structured_answer.get("citations", [
                {
                    "section": h["source"]["section"],
                    "pages": h["source"]["pages"],
                }
                for h in used_hits[:3]
            ])
        })
        
        print(f"✅ 최종 답변 생성 완료 [session={session_id}]")


# ========================================
# 새로운 Clarify 루프 처리 (작업자 질문 + LLM 답변)
# ========================================

async def process_clarify_qa_turn(session_id: str, user_question: str):
    """
    Streaming STT 세션 중 Clarify 질문/답변 턴 처리:
    1. 히스토리 컨텍스트 구성
    2. Hybrid Search + Rerank (RAG 기반)
    3. Evidence Check (RED/YELLOW/GREEN) - RAG 기반 판단
    4. RED/YELLOW → Clarify 질문 생성 (Gemini-Flash) 및 LLM 답변 생성
    5. TTS 변환 후 clarify_qa_turn 이벤트 전송
    6. GREEN → GPT-4o로 최종 답변 생성 + TTS + 모바일 전송
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
        # 1. 히스토리 컨텍스트 구성 (이전 대화 기록 반영)
        history_context = ""
        user_lines = []
        clarify_lines = []  # Clarify 질문/답변도 포함
        
        for ev in reversed(history):
            role = ev.get("role")
            event_type = ev.get("type")
            data = ev.get("data", {})
            
            # 사용자 질문 (스트리밍 STT)
            if role == "user" and event_type == "streaming_stt":
                text = data.get("text", "")
                if text:
                    user_lines.append(text)
            
            # Clarify 질문/답변 (시스템)
            elif role == "system" and event_type == "clarify":
                clarify_guidance = data.get("clarify_guidance", "")
                if clarify_guidance:
                    clarify_lines.append(f"시스템 질문: {clarify_guidance}")
            
            if len(user_lines) >= 2:  # 최근 2개 질문 사용
                break
        
        if user_lines:
            history_context = " \n".join(reversed(user_lines))
        
        # Clarify 맥락 추가 (이전 Clarify 질문 반영)
        if clarify_lines:
            history_context += "\n\n" + "\n".join(reversed(clarify_lines[-2:]))  # 최근 2개 Clarify 포함
        
        effective_query = f"{history_context} \n{user_question}" if history_context else user_question
        normalized_query = normalize_query_style(effective_query)
        
        # 2. Hybrid Search + Rerank (RAG 기반)
        print("=" * 60)
        print(f"🔍 [단계 13-2] Hybrid Search + Rerank 시작")
        print(f"   정규화된 쿼리: {normalized_query[:50]}...")
        print("=" * 60)
        base_hits = hybrid_retrieve(normalized_query, top_k=8)
        hits = rerank(normalized_query, base_hits, top_k=6)
        used_hits = hits[:5]
        print(f"✅ Hybrid Search + Rerank 완료: {len(hits)}개 문서 검색")
        await wait_for_next_step("Hybrid Search + Rerank 완료", "13-2")
        
        if not hits:
            await broadcast_to("mobile", "clarify_qa_turn", {
                "session_id": session_id,
                "turn_id": turn_id,
                "user_question": user_question,
                "llm_answer": "관련 문서를 찾을 수 없습니다.",
                "audio_content": None,
                "audio_encoding": None,
                "need_clarify": True,
                "status": "error"
            })
            return
        
        # 3. RAG 기반 Evidence Check (RED/YELLOW/GREEN)
        print("=" * 60)
        print(f"🔍 [단계 13-3] Evidence Check 시작 (RED/YELLOW/GREEN 판단)")
        print("=" * 60)
        need_clarify, evidence_stats = comprehensive_evidence_check(effective_query, used_hits)
        gate_decision = evidence_stats.get("gate_decision")
        print(f"✅ Evidence Check 완료: gate_decision={gate_decision}, need_clarify={need_clarify}")
        print("=" * 60)
        await wait_for_next_step("Evidence Check 완료", "13-3")
        
        # 히스토리를 evidence_stats에 포함 (make_clarify_prompt에서 사용)
        evidence_stats["history"] = history
        
        # RED/YELLOW → Clarify 질문 생성
        if need_clarify or gate_decision != "GREEN":
            # RAG 기반 Clarify 질문 생성 (Gemini-Flash 사용)
            from app.services.answerability import make_clarify_prompt
            
            print("=" * 60)
            print(f"💬 [단계 13-4] Clarify 질문 생성 시작 (RED/YELLOW)")
            print("=" * 60)
            clarified_result = make_clarify_prompt(effective_query, used_hits, evidence_stats)
            clarify_question = clarified_result.get("guide", "문제 상황을 구체적으로 말씀해주세요.")
            print(f"✅ Clarify 질문 생성 완료: {clarify_question[:50]}...")
            await wait_for_next_step("Clarify 질문 생성 완료", "13-4")
            
            # LLM 답변 생성 (Gemini-Flash 사용)
            print("=" * 60)
            print(f"🤖 [단계 13-5] LLM 답변 생성 시작 (Gemini-Flash)")
            print("=" * 60)
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
            print(f"✅ LLM 답변 생성 완료: {llm_answer[:50]}...")
            await wait_for_next_step("LLM 답변 생성 완료", "13-5")
            
            # TTS 변환
            print("=" * 60)
            print(f"🔊 [단계 13-6] TTS 변환 시작")
            print(f"   LLM 답변: {llm_answer[:50]}...")
            print("=" * 60)
            try:
                tts_result = text_to_speech(llm_answer)
                audio_content = tts_result.get("audio_content")
                audio_encoding = tts_result.get("mime_type")
                print(f"✅ TTS 변환 완료: {len(audio_content) if audio_content else 0} bytes")
            except Exception as e:
                print(f"⚠️ TTS 생성 실패: {e}")
                audio_content = None
                audio_encoding = None
            await wait_for_next_step("TTS 변환 완료", "13-6")
            
            # Redis에 저장
            memory.append_event(session_id, {
                "role": "system",
                "type": "clarify",
                "data": {
                    "turn_id": turn_id,
                    "gate_decision": gate_decision,
                    "clarify_guidance": clarify_question,
                    "evidence_stats": evidence_stats
                }
            })
            
            # clarify_qa_turn 이벤트 전송
            print("=" * 60)
            print(f"📤 [단계 13-7] 모바일로 clarify_qa_turn 이벤트 전송 시작")
            print(f"   Turn ID: {turn_id}, Need Clarify: True, Gate Decision: {gate_decision}")
            print("=" * 60)
            await broadcast_to("mobile", "clarify_qa_turn", {
                "session_id": session_id,
                "turn_id": turn_id,
                "user_question": user_question,
                "llm_answer": llm_answer,
                "audio_content": audio_content,
                "audio_encoding": audio_encoding,
                "need_clarify": True,
                "gate_decision": gate_decision,
                "status": "success",
                "evidence_trace": evidence_stats.get("evidence_trace", {}),
                "missing_info": evidence_stats.get("missing_info", [])
            })
            print("=" * 60)
            print(f"✅ [단계 13-7 완료] 모바일로 clarify_qa_turn 이벤트 전송 완료")
            print("=" * 60)
            await wait_for_next_step("모바일로 clarify_qa_turn 이벤트 전송 완료", "13-7")
            
            # 세션 정보 업데이트
            clarify_sessions[session_id]["turns"].append({
                "turn_id": turn_id,
                "user_question": user_question,
                "llm_answer": llm_answer,
                "need_clarify": True,
                "gate_decision": gate_decision
            })
            
            print(f"📤 Clarify 질문/답변 턴 {turn_id} 전송 [session={session_id}]: gate_decision={gate_decision}, need_clarify=True")
            
        else:
            # GREEN → 최종 답변 생성 (GPT-4o)
            # 이미 위에서 RAG 검색 및 Evidence Check 완료됨
            print("=" * 60)
            print(f"✅ [단계 13-8] 최종 답변 생성 시작 (GREEN, GPT-4o)")
            print("=" * 60)
            
            # 최종 답변 생성 (GPT-4o) - 구조화된 답변 + TTS 친화적
            snippets = [h["source"]["content"] for h in used_hits]
            answer_result = llm_generate_answer(effective_query, snippets, used_hits)
            print(f"✅ 최종 답변 생성 완료: {answer_result.get('tts_text', '')[:50]}...")
            await wait_for_next_step("최종 답변 생성 완료 (GPT-4o)", "13-8")
            
            # 구조화된 답변에서 TTS 텍스트 추출
            answer_text = answer_result.get("tts_text") or answer_result.get("summary") or answer_result.get("answer", "")
            structured_answer = answer_result  # 전체 구조화된 답변
            
            # TTS 생성 (TTS 친화적 텍스트 사용)
            print("=" * 60)
            print(f"🔊 [단계 13-9] 최종 답변 TTS 변환 시작")
            print("=" * 60)
            try:
                tts_result = text_to_speech(answer_text)
                audio_content = tts_result.get("audio_content")
                audio_encoding = tts_result.get("mime_type")
                print(f"✅ 최종 답변 TTS 변환 완료: {len(audio_content) if audio_content else 0} bytes")
            except Exception as e:
                print(f"⚠️ TTS 생성 실패: {e}")
                audio_content = None
                audio_encoding = None
            await wait_for_next_step("최종 답변 TTS 변환 완료", "13-9")
            
            # Redis에 저장
            memory.append_event(session_id, {
                "role": "assistant",
                "type": "final_answer",
                "data": {
                    "answer": answer_text,
                    "structured_answer": structured_answer,
                    "citations": structured_answer.get("citations", [
                        {
                            "section": h["source"]["section"],
                            "pages": h["source"]["pages"],
                        }
                        for h in used_hits[:3]
                    ])
                }
            })
            
            # 세션 초기화
            memory.clear_history(session_id)
            clarify_sessions.pop(session_id, None)
            
            # 최종 답변 전송 (구조화된 답변 포함)
            print("=" * 60)
            print(f"📤 [단계 13-10] 모바일로 final_answer 이벤트 전송 시작")
            print("=" * 60)
            await broadcast_to("mobile", "final_answer", {
                "session_id": session_id,
                "turn_id": turn_id,
                "status": "completed",
                "answer": answer_text,  # TTS 친화적 텍스트
                "structured_answer": structured_answer,  # 전체 구조화된 답변 (UI 표시용)
                "audio_content": audio_content,
                "audio_encoding": audio_encoding,
                "citations": structured_answer.get("citations", [
                    {
                        "section": h["source"]["section"],
                        "pages": h["source"]["pages"],
                    }
                    for h in used_hits[:3]
                ])
            })
            print("=" * 60)
            print(f"✅ [단계 13-10 완료] 모바일로 final_answer 이벤트 전송 완료")
            print(f"   최종 답변 생성 완료 [session={session_id}]")
            print("=" * 60)
            await wait_for_next_step("모바일로 final_answer 이벤트 전송 완료", "13-10")
            
            # 서비스 완료: 라즈베리파이로 서비스 종료 이벤트 전송 (wakeword 재활성화 신호)
            print("=" * 60)
            print(f"📤 [단계 13-11] 라즈베리파이로 서비스 완료 이벤트 전송 시작")
            print("=" * 60)
            await broadcast_to("raspi", "service_completed", {
                "session_id": session_id,
                "status": "completed"
            })
            print("=" * 60)
            print(f"✅ [단계 13-11 완료] 라즈베리파이로 서비스 완료 이벤트 전송 완료")
            print("=" * 60)
            
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
    """라즈베리파이 → JPEG binary 수신 후 모션 추정 및 AR 마커 업데이트"""
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown" or not data:
        return

    np_data = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
    if frame is None:
        print("⚠️ Failed to decode frame")
        return

    # 1️⃣ 모션 계산 (Optical Flow + Essential)
    result = await motion_core.process_frame(frame, sid=sid)
    if result["status"] not in ("ok", "init"):
        # 모션 추정 불가한 경우 스킵
        _, jpeg_bytes = cv2.imencode(".jpg", frame)
        await broadcast_to("pc", "video_frame", jpeg_bytes.tobytes())
        return

    # 2️⃣ AR 마커 업데이트 (Affine + Depth 기반)
    if ar_markers:
        updated_markers = []

        for m in ar_markers:
            info = m.get("info", {})
            u = float(info.get("x", 0.0))
            v = float(info.get("y", 0.0))

            # === 📍 Optical Flow + Essential 기반 위치/깊이 보정 ===
            u_new, v_new, z_new = motion_core.update_marker_position(u, v)

            # === 📏 깊이에 따른 크기 계산 (z 클수록 가까움 → 커짐) ===
            base_size = 30.0
            scale_factor = 20.0
            size_px = np.clip(base_size + (z_new * scale_factor), 10.0, 100.0)

            # === 🎯 패치 매칭 기반 보정 (선택) ===
            tpl = info.get("tpl", None)
            if tpl is not None and tpl.size > 0:
                gray_now = motion_core.get_latest_gray()
                if gray_now is not None:
                    u_ref, v_ref, score = motion_core.refine_patch_position(
                        gray_now, u_new, v_new, tpl, search_r=14
                    )
                    if score >= 0.75:
                        u_new, v_new = u_ref, v_ref
                        # 템플릿 최신화
                        new_patch = motion_core.extract_patch_from_current_gray(u_new, v_new, 10)
                        if new_patch is not None:
                            info["tpl"] = cv2.addWeighted(tpl, 0.9, new_patch, 0.1, 0)

            updated_markers.append({
                "idx": m["idx"],
                "info": {
                    "x": round(u_new, 2),
                    "y": round(v_new, 2),
                    "z": round(z_new, 3),
                    "size": round(size_px, 3),
                    "tpl": info.get("tpl", None)
                }
            })

        # === ✅ 전역 마커 리스트 갱신 ===
        ar_markers[:] = updated_markers

        # === 🛰️ 클라이언트로 전송 ===
        await broadcast_to("pc", "ar-info", {"markers": ar_markers})

    # 3️⃣ 프레임 브로드캐스트 (PC 디스플레이용)
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

# ========================================
# AR 마커 생성 이벤트
# ========================================
# 전역 관리 리스트
ar_markers = []  # [{ "idx": int, "info": { "x": float, "y": float, "size": float } }, ...]

async def handle_ar_marker(sid, data):
    """
    웹페이지에서 AR 마커 생성을 요청하면,
    클릭된 (x, y) 좌표를 기반으로 월드좌표(x, y, z)를 계산하고
    상대 크기(size)를 추정해 저장 및 클라이언트로 전송합니다.
    """
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown":
        print("⚠️ Unknown sender")
        return

    marker_x = data.get("marker_x")
    marker_y = data.get("marker_y")

    # === 1️⃣ Optical Flow + Essential 기반 좌표/깊이 업데이트 ===
    u_new, v_new, z_new = motion_core.update_marker_position(marker_x, marker_y)

    # === 2️⃣ 크기 계산 (z 클수록 커짐)
    base_size = 30.0
    scale_factor = 10.0
    size_px = np.clip(base_size + (z_new * scale_factor), 10.0, 100.0)

    # === 3️⃣ 마커 저장 ===
    marker_info = {
        "idx": len(ar_markers) + 1,
        "info": {
            "x": u_new,
            "y": v_new,
            "z": z_new,
            "size": round(size_px, 2),
        }
    }
    ar_markers.append(marker_info)

    # === 4️⃣ 로그 및 전송 ===
    print(f"📍 Marker idx={marker_info['idx']} | pos=({u_new:.1f},{v_new:.1f}) | z={z_new:.3f} | size={size_px:.1f}")
    await sio.emit("ar-info", {"markers": ar_markers}, to=sid)