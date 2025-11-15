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
from datetime import datetime
from typing import Dict, Any, Optional
from app.services.intent_service import classify_intent
from app.services import memory
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.answerability import comprehensive_evidence_check, normalize_query_style
from app.services.generator import llm_generate_answer
from app.services.tts_service import text_to_speech
from app.services.llm_service import clarify_query
from app.ar import motion_core
import httpx

YOLO_URL = os.getenv("YOLO_SERVICE_URL", "http://vision:9000")

async def run_anomaly_detection():

    url = f"{YOLO_URL}/analyze"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(url, json={"trigger": "run"})
        res.raise_for_status()
        return res.json()

async def stop_device_detector_task():
    async with httpx.AsyncClient() as client:
        await client.post(f"{YOLO_URL}/device/stop")

async def start_device_detector_task():
    async with httpx.AsyncClient() as client:
        await client.post(f"{YOLO_URL}/device/start")

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

# Intent 결과 저장 (CV 로직 실행 대기용)
pending_intents: Dict[str, str] = {}  # { session_id 또는 임시 키: "AI_SUPPORTER" | "OPERATOR" }


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
        # print("❌ ERROR: sio 인스턴스가 None입니다!")
        return
    
    # print(f"🔍 Socket.IO 서버 인스턴스 확인: {sio}")
    
    # 이벤트 핸들러 등록 (데코레이터 대신 직접 등록)
    sio.on("connect")(handle_connect)
    sio.on("disconnect")(handle_disconnect)
    sio.on("register_device")(handle_register_device)
    sio.on("stt_result")(handle_stt_result)
    sio.on("wakeword_detected")(handle_wakeword_detected)  # 라즈베리파이에서 Wakeword 감지 이벤트 수신
    sio.on("wakeword_audio_completed")(handle_wakeword_audio_completed)  # 모바일에서 음성 파일 재생 완료 이벤트 수신
    sio.on("intent_audio_completed")(handle_intent_audio_completed)  # 모바일에서 Intent 음성 파일 재생 완료 이벤트 수신 (AI_SUPPORTER용)
    sio.on("audio_playback_completed")(handle_audio_playback_completed)  # 모바일에서 오디오 재생 완료 이벤트 수신 (CV 탐지 실패, Clarify Q&A 턴 등)
    sio.on("start_clarify_session")(handle_start_clarify_session)
    sio.on("end_clarify_session")(handle_end_clarify_session)
    sio.on("clarify_response")(handle_clarify_response)  # 모바일에서 오는 Clarify 응답 수신
    sio.on("clarify_input")(handle_clarify_input)  # 모바일에서 오는 Clarify 입력 수신 (Socket.IO를 통해)
    sio.on("control_raspi")(handle_control_raspi)  # 모바일에서 라즈베리파이 제어 명령
    sio.on("video_frame")(handle_video_frame)
    sio.on("audio_frame")(handle_audio_frame)  
    sio.on("ar-marker")(handle_ar_marker)
    sio.on("delete-marker")(delete_marker)
    


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
        # print(f"⚠️ [broadcast_to] 연결된 디바이스가 없습니다.")
        # print(f"   요청 디바이스: {device_types}")
        # print(f"   현재 연결된 디바이스: {list(set(device_map.values()))}")
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
        # print("=" * 60)
        # print(f"✅ [연결] Client connected: {sid[:15]}... (from {remote_addr})")
        # print(f"   User-Agent: {user_agent[:50]}...")
        # print(f"   현재 연결된 디바이스 수: {len(device_map)}")
        print("=" * 60)
        
        if sio:
            await sio.emit("server_message", {"msg": "Connected"}, to=sid)
        # 연결 허용 (명시적으로 True 반환하거나 아무것도 반환하지 않으면 허용)
        # print(f"🔍 [DEBUG] handle_connect 성공, 연결 허용")
        return True
    except Exception as e:
        # print(f"❌ Connection error for {sid}: {e}")
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
    print(f"🔗 [디바이스 등록] Registered device: {device} ({sid[:15]}...)")
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
    print("=" * 60)
    print(f"🔔 [이벤트 수신] wakeword_detected 이벤트 도착")
    print(f"   SID: {sid[:15]}...")
    print(f"   Data: {data}")
    print(f"   현재 device_map: {dict(device_map)}")
    print(f"   연결된 디바이스: {list(set(device_map.values()))}")
    print("=" * 60)

    await stop_device_detector_task()
    print("✅ 기기 탐지 종료")
    sender_device = device_map.get(sid, "unknown")
    print(f"   발신자 디바이스: {sender_device}")
    
    # 라즈베리파이에서만 받음
    if sender_device != "raspi":
        print("=" * 60)
        print(f"⚠️ [오류] Wakeword 감지 이벤트는 라즈베리파이에서만 받을 수 있습니다.")
        print(f"   수신자: {sender_device}")
        print(f"   현재 device_map: {dict(device_map)}")
        print(f"   연결된 디바이스: {list(set(device_map.values()))}")
        print("=" * 60)
        return
    
    print("=" * 60)
    print(f"📝 [단계 2-1] FastAPI 서버: Wakeword 감지 이벤트 수신 [raspi]")
    print("=" * 60)
    await wait_for_next_step("Wakeword 감지 이벤트 수신 완료", "2-1")
    
    # 모바일 연결 상태 확인
    mobile_sids = [s for s, d in device_map.items() if d == "mobile"]
    if not mobile_sids:
        print("=" * 60)
        print("⚠️ [오류] 모바일 디바이스가 연결되어 있지 않습니다.")
        print(f"   현재 연결된 디바이스: {list(set(device_map.values()))}")
        print("=" * 60)
        return
    
    print("=" * 60)
    print(f"✅ 모바일 디바이스 연결 확인: {len(mobile_sids)}개")
    print(f"   모바일 SID: {[s[:15] + '...' for s in mobile_sids]}")
    print("=" * 60)
    
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
    print("=" * 60)
    print(f"🔔 [이벤트 수신] wakeword_audio_completed 이벤트 도착")
    print(f"   SID: {sid[:15]}...")
    print(f"   Data: {data}")
    print(f"   현재 device_map: {dict(device_map)}")
    print(f"   연결된 디바이스: {list(set(device_map.values()))}")
    print("=" * 60)
    
    sender_device = device_map.get(sid, "unknown")
    print(f"   발신자 디바이스: {sender_device}")
    
    # 모바일에서만 받음
    if sender_device != "mobile":
        print("=" * 60)
        print(f"⚠️ [오류] 음성 파일 재생 완료 이벤트는 모바일에서만 받을 수 있습니다.")
        print(f"   수신자: {sender_device}")
        print(f"   현재 device_map: {dict(device_map)}")
        print(f"   연결된 디바이스: {list(set(device_map.values()))}")
        print("=" * 60)
        return
    
    print("=" * 60)
    print(f"📝 [단계 2-2] FastAPI 서버: 모바일 음성 파일 재생 완료 이벤트 수신 [mobile]")
    print("=" * 60)
    await wait_for_next_step("모바일 음성 파일 재생 완료 이벤트 수신 완료", "2-2")
    
    # 라즈베리파이 연결 상태 확인
    raspi_sids = [s for s, d in device_map.items() if d == "raspi"]
    if not raspi_sids:
        print("=" * 60)
        print("⚠️ [오류] 라즈베리파이 디바이스가 연결되어 있지 않습니다.")
        print(f"   현재 연결된 디바이스: {list(set(device_map.values()))}")
        print("=" * 60)
        return
    
    print("=" * 60)
    print(f"✅ 라즈베리파이 디바이스 연결 확인: {len(raspi_sids)}개")
    print(f"   라즈베리파이 SID: {[s[:15] + '...' for s in raspi_sids]}")
    print("=" * 60)
    
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


async def handle_intent_audio_completed(sid, data):
    """
    모바일로부터 Intent 음성 파일 재생 완료 이벤트 수신
    AI_SUPPORTER인 경우 CV 로직 실행
    """
    print("=" * 60)
    print(f"🔔 [이벤트 수신] intent_audio_completed 이벤트 도착")
    print(f"   SID: {sid[:15]}...")
    print(f"   현재 device_map: {dict(device_map)}")
    print("=" * 60)
    
    sender_device = device_map.get(sid, "unknown")
    print(f"   발신자 디바이스: {sender_device}")
    
    # 모바일에서만 받음
    if sender_device != "mobile":
        print(f"⚠️ Intent 음성 파일 재생 완료 이벤트는 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        print(f"   현재 device_map: {dict(device_map)}")
        return
    
    intent = data.get("intent", "").upper()
    
    print("=" * 60)
    print(f"📝 [단계 8-1] FastAPI 서버: 모바일 Intent 음성 파일 재생 완료 이벤트 수신 [mobile]")
    print(f"   Intent: {intent}")
    print("=" * 60)
    await wait_for_next_step("모바일 Intent 음성 파일 재생 완료 이벤트 수신 완료", "8-1")
    
    # AI_SUPPORTER인 경우 CV 모델 실행
    if intent == "AI_SUPPORTER":
        try:
            print("=" * 60)
            print("🔍 [단계 9] CV 모델 실행 시작")
            print("=" * 60)

            cv_raw = await run_anomaly_detection()
            print("CV 결과:", cv_raw)

            modules = cv_raw.get("modules", [])
            anomalies = cv_raw.get("anomalies", {}).get("results", {})
            has_anomaly = cv_raw.get("anomalies", {}).get("status") == "anomaly_detected"

            cv_result = {
                "detected": has_anomaly,
                "device_type": cv_raw.get("device_type"),
                "modules": modules,
                "anomalies": {
                    "status": "anomaly_detected" if has_anomaly else "no_anomaly",
                    "results": anomalies
                },
                "message": cv_raw.get("message", "")
            }

                
            # CV 결과 상세 출력
            print("=" * 60)
            print("📊 [단계 9-2 완료] CV 모델 실행 결과")
            print(f"   탐지 여부: {cv_result.get('detected', False)}")
            print(f"   장비 타입: {cv_result.get('device_type', 'unknown')}")
            print(f"   탐지된 모듈 수: {len(cv_result.get('modules', []))}")
            if cv_result.get('modules'):
                module_names = [m.get('label', 'unknown') for m in cv_result.get('modules', [])]
                print(f"   모듈 목록: {', '.join(module_names)}")
            anomalies = cv_result.get('anomalies', {})
            if anomalies:
                anomaly_status = anomalies.get('status', 'unknown')
                print(f"   이상 탐지 상태: {anomaly_status}")
                if isinstance(anomalies.get('results'), dict):
                    anomaly_results = anomalies.get('results', {})
                    print(f"   이상 탐지 모듈 수: {len(anomaly_results)}개")
                    for module_name, module_result in anomaly_results.items():
                        if isinstance(module_result, dict):
                            module_status = module_result.get('status', 'unknown')
                            module_msg = module_result.get('message', '')
                            print(f"     - {module_name}: {module_status} ({module_msg})")
            print(f"   메시지: {cv_result.get('message', '')}")
            print("=" * 60)
            
            await wait_for_next_step("CV 모델 실행 완료", "9")
            
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
                print(f"✅ CV 모델 오류 탐지 성공: {cv_result.get('message', '')}")
                print("=" * 60)
                await wait_for_next_step("CV 모델 오류 탐지 성공", "9")
                
                # CV 탐지 결과를 기반으로 RAG 쿼리 생성
                device_type = cv_result.get("device_type", "unknown")
                anomalies = cv_result.get("anomalies", {})
                modules = cv_result.get("modules", [])
                
                # 오류 내용을 쿼리로 변환
                query_parts = []
                if device_type and device_type != "unknown":
                    query_parts.append(f"{device_type}에서")
                
                if anomalies and isinstance(anomalies, dict):
                    anomaly_status = anomalies.get("status", "")
                    if anomaly_status == "anomaly_detected":
                        results = anomalies.get("results", {})
                        detected_modules = []
                        for module_name, module_result in results.items():
                            if isinstance(module_result, dict) and module_result.get("status") == "anomaly":
                                detected_modules.append(module_name)
                        if detected_modules:
                            query_parts.append(f"{', '.join(detected_modules)}에서 이상이 탐지되었습니다")
                    else:
                        query_parts.append("이상이 탐지되었습니다")
                else:
                    query_parts.append("이상이 탐지되었습니다")
                
                query = " ".join(query_parts) if query_parts else "CV 모델에서 이상이 탐지되었습니다"
                
                print("=" * 60)
                print(f"🔍 [단계 10] CV 탐지 결과 기반 RAG 쿼리 생성")
                print(f"   Query: {query}")
                print("=" * 60)
                await wait_for_next_step("RAG 쿼리 생성 완료", "10")
                
                # RAG 검색 (Hybrid Retrieve + Rerank)
                print("=" * 60)
                print(f"📚 [단계 11] RAG 검색 시작 (Hybrid Retrieve + Rerank)")
                print("=" * 60)
                try:
                    from app.core.config import settings
                    base_hits = hybrid_retrieve(query, top_k=settings.TOP_K)
                    hits = rerank(query, base_hits, top_k=settings.RERANK_TOP_K)
                    used_hits = hits[:5]
                    
                    if not used_hits:
                        print("⚠️ RAG 검색 결과가 없습니다.")
                        answer_text = f"{query}에 대한 관련 문서를 찾을 수 없습니다."
                        structured_answer = {
                            "summary": answer_text,
                            "tts_text": answer_text,
                            "citations": []
                        }
                    else:
                        print(f"✅ RAG 검색 완료: {len(used_hits)}개 문서 발견")
                        await wait_for_next_step("RAG 검색 완료", "11")
                        
                        # GPT-4o로 최종 답변 생성
                        print("=" * 60)
                        print(f"🤖 [단계 12] GPT-4o로 최종 답변 생성 시작")
                        print("=" * 60)
                        
                        # GPT-4o 호출 시점에 Streaming STT 세션 종료 이벤트 전송
                        # 주의: 마이크는 계속 ON 상태이지만, Streaming STT 세션을 종료하여 큐에 데이터가 누적되지 않도록 함
                        print("[DEBUG] GPT-4o 호출 시점: Streaming STT 세션 종료 이벤트 전송")
                        # CV 탐지 성공은 세션이 없으므로 세션 종료 이벤트는 전송하지 않음
                        # (이 경우는 Streaming STT가 실행되지 않았으므로)
                        
                        snippets = [h["source"]["content"] for h in used_hits]
                        answer_result = llm_generate_answer(query, snippets, used_hits)
                        answer_text = answer_result.get("tts_text") or answer_result.get("summary") or answer_result.get("answer", "")
                        structured_answer = answer_result
                        print(f"✅ 최종 답변 생성 완료: {answer_text[:50]}...")
                        await wait_for_next_step("최종 답변 생성 완료 (GPT-4o)", "12")
                except Exception as e:
                    print(f"❌ RAG 검색 또는 답변 생성 실패: {e}")
                    import traceback
                    traceback.print_exc()
                    answer_text = f"{query}에 대한 답변을 생성하는 중 오류가 발생했습니다."
                    structured_answer = {
                        "summary": answer_text,
                        "tts_text": answer_text,
                        "citations": []
                    }
                
                # TTS 변환
                print("=" * 60)
                print(f"🔊 [단계 13] 최종 답변 TTS 변환 시작")
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
                await wait_for_next_step("최종 답변 TTS 변환 완료", "13")
                
                # 모바일로 최종 답변 전송 (텍스트 + TTS 음성 파일)
                print("=" * 60)
                print(f"📤 [단계 14] 모바일로 최종 답변 전송 시작")
                print("=" * 60)
                await broadcast_to("mobile", "final_answer", {
                    "session_id": None,  # CV 탐지 성공은 세션이 없음
                    "turn_id": 1,
                    "status": "completed",
                    "answer": answer_text,
                    "structured_answer": structured_answer,
                    "audio_content": audio_content,
                    "audio_encoding": audio_encoding,
                    "citations": structured_answer.get("citations", []),
                    "cv_detection_result": {
                        "device_type": device_type,
                        "modules": modules,
                        "anomalies": anomalies,
                        "message": cv_result.get('message', '')
                    }
                })
                print("✅ 모바일로 최종 답변 전송 완료")
                print("=" * 60)
                await wait_for_next_step("모바일로 최종 답변 전송 완료", "14")
                
                # 라즈베리파이로 CV 탐지 성공 알림 (기존 로직 유지)
                # CV 탐지 성공 시 마이크는 OFF 상태 유지 (켜지 않음)
                await broadcast_to("raspi", "cv_detection_success", cv_result.get('message', ''))
        except Exception as e:
            print(f"❌ CV 모델 실행 오류: {e}")
            import traceback
            traceback.print_exc()
    
            # CV 모델 오류 시에도 탐지 실패로 처리
            await broadcast_to("mobile", "cv_detection_failed", {
                "message": "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다."
            })
            await broadcast_to("raspi", "cv_detection_failed", {
                "message": "오류를 탐지하지 못했습니다. Streaming STT 세션을 시작하세요."
            })
    elif intent == "OPERATOR":
        # OPERATOR인 경우 WebRTC 오디오 스트리밍 대기 상태
        print("=" * 60)
        print(f"✅ [단계 8-1 완료] OPERATOR Intent 음성 파일 재생 완료 확인")
        print("   WebRTC 오디오 스트리밍 대기 중 (accept_communication 이벤트 대기)")
        print("=" * 60)
        
        # 주의: 마이크는 하나이며, STT 프로세스가 마이크를 해제한 후 WebRTC가 시작되어야 합니다.
        # 버퍼링 STT 완료 후 이미 mic.pause()가 호출되어 STT 목적 음성 수집은 OFF 상태입니다.
        # 실제 마이크 장치 해제는 accept_communication 이벤트에서 handle_audio_stream으로 처리됩니다.
        
        print("✅ OPERATOR Intent 음성 파일 재생 완료 처리 완료")
        print("   💡 accept_communication 이벤트 수신 시 WebRTC 오디오 스트리밍이 시작됩니다.")
        print("=" * 60)
    else:
        print(f"ℹ️ Intent '{intent}'는 CV 로직을 실행하지 않습니다.")


async def handle_audio_playback_completed(sid, data):
    """
    모바일로부터 오디오 재생 완료 이벤트 수신
    - type="cv_detection_failed": CV 탐지 실패 음성 파일 재생 완료 → 라즈베리파이로 Streaming STT 시작 신호
    - type="clarify_qa_turn": Clarify Q&A 턴 TTS 재생 완료 → 다음 Streaming STT 질문 대기
    """
    sender_device = device_map.get(sid, "unknown")
    
    # 모바일에서만 받음
    if sender_device != "mobile":
        print(f"⚠️ 오디오 재생 완료 이벤트는 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    audio_type = data.get("type", "")
    session_id = data.get("session_id")
    turn_id = data.get("turn_id")
    
    print("=" * 60)
    print(f"📝 FastAPI 서버: 모바일 오디오 재생 완료 이벤트 수신 [mobile]")
    print(f"   Type: {audio_type}, Session ID: {session_id}, Turn ID: {turn_id}")
    print("=" * 60)
    await wait_for_next_step("모바일 오디오 재생 완료 이벤트 수신 완료", "12-1")
    
    if audio_type == "cv_detection_failed":
        # CV 탐지 실패 음성 파일 재생 완료 → 라즈베리파이로 Streaming STT 시작 신호
        print("=" * 60)
        print("📡 라즈베리파이로 Streaming STT 시작 신호 전송")
        print("=" * 60)
        
        # 세션 ID 생성 (Clarify 세션용)
        import uuid
        session_id = str(uuid.uuid4())
        
        await broadcast_to("raspi", "start_streaming_stt", {
            "session_id": session_id,
            "message": "모바일 CV 탐지 실패 음성 파일 재생 완료. Streaming STT 세션을 시작하세요."
        })
        print(f"✅ 라즈베리파이로 Streaming STT 시작 신호 전송 완료: session_id={session_id}")
        await wait_for_next_step("라즈베리파이로 Streaming STT 시작 신호 전송 완료", "12-2")
        
    elif audio_type == "clarify_qa_turn":
        # Clarify Q&A 턴 TTS 재생 완료 → 다음 Streaming STT 질문 대기
        # (이미 라즈베리파이에서 Streaming STT가 실행 중이므로 별도 처리 불필요)
        print("=" * 60)
        print(f"✅ Clarify Q&A 턴 TTS 재생 완료: session_id={session_id}, turn_id={turn_id}")
        print("   다음 Streaming STT 질문을 대기 중입니다.")
        print("=" * 60)
        await wait_for_next_step("Clarify Q&A 턴 TTS 재생 완료 처리", "12-3")
    elif audio_type == "final_answer":
        # AI_Supporter 최종 답변 TTS 재생 완료 → 마이크 ON + Wakeword 감지 대기 시작
        print("=" * 60)
        print(f"✅ AI_Supporter 최종 답변 TTS 재생 완료: session_id={session_id}")
        print("   Wakeword 감지 대기 시작 이벤트 전송")
        print("=" * 60)
        
        
        # 라즈베리파이로 Wakeword 감지 대기 시작 이벤트 전송
        await broadcast_to("raspi", "wakeword_start_waiting", {})
        
        print("✅ STT 목적 음성 수집 재개 + Wakeword 감지 대기 시작 이벤트 전송 완료")
        await wait_for_next_step("최종 답변 TTS 재생 완료 처리", "14-1")
    else:
        print(f"ℹ️ 알 수 없는 오디오 타입: {audio_type}")


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
    print("=" * 60)
    print(f"🔔 [이벤트 수신] stt_result 이벤트 도착")
    print(f"   SID: {sid[:15]}...")
    print(f"   현재 device_map: {dict(device_map)}")
    print("=" * 60)
    
    sender_device = device_map.get(sid, "unknown")
    print(f"   발신자 디바이스: {sender_device}")
    
    # 라즈베리파이에서만 받음
    if sender_device != "raspi":
        print(f"⚠️ STT 결과는 라즈베리파이에서만 받을 수 있습니다. 수신자: {sender_device}")
        print(f"   현재 device_map: {dict(device_map)}")
        return
    
    stt_type = data.get("type", "unknown")
    stt_text = data.get("text", "").strip()
    confidence = data.get("confidence")
    session_id = data.get("session_id")  # Clarify 세션 ID (있는 경우)
    
    print("=" * 60)
    print(f"📝 [단계 6] FastAPI 서버: STT 결과 수신 [raspi]")
    print(f"   타입: {stt_type}, 텍스트: {stt_text[:50]}...")
    print(f"   Session ID: {session_id}")
    print(f"   Confidence: {confidence}")
    print("=" * 60)
    await wait_for_next_step("STT 결과 수신 완료", "6")
    
    # 버퍼링 STT (type="final"이고 session_id가 없음)
    if stt_type == "final" and not session_id:
        print("=" * 60)
        print("✅ 버퍼링 STT 확인: type=final, session_id=None")
        print(f"   텍스트: '{stt_text[:50]}...'")
        print("=" * 60)
        
        # STT 텍스트가 비어있으면 처리 불가
        if not stt_text:
            print("⚠️ STT 텍스트가 비어있습니다. Intent 분류를 수행할 수 없습니다.")
            return
        
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
            
            # 버퍼링 STT 세션 종료 이벤트 전송
            # 주의: 마이크는 계속 ON 상태이지만, 버퍼링 STT 세션은 종료하여 큐에 데이터가 누적되지 않도록 함
            print("=" * 60)
            print("📤 [단계 8-0] 버퍼링 STT 세션 종료 이벤트 전송")
            print("=" * 60)
            await broadcast_to("raspi", "stop_buffered_stt", {
                "reason": "버퍼링 STT 결과 전송 완료, Intent 분류 진행"
            })
            print("✅ 버퍼링 STT 세션 종료 이벤트 전송 완료")
            await wait_for_next_step("버퍼링 STT 세션 종료 이벤트 전송 완료", "8-0")
            
            # AI_SUPPORTER인 경우 모바일에서 intent_audio_completed 이벤트를 기다림
            # CV 로직은 handle_intent_audio_completed에서 실행됨
            if intent == "AI_SUPPORTER":
                print("=" * 60)
                print("⏳ [단계 8-1] 모바일 AI_SUPPORTER 음성 파일 재생 완료 이벤트 대기 중...")
                print("   💡 모바일에서 'AI_Supporter 기능을 시작합니다. 오류 탐지.' 재생 중...")
                print("   💡 재생 완료 시 intent_audio_completed 이벤트를 통해 CV 로직이 실행됩니다.")
                print("=" * 60)



                    
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
            # GPT-4o 호출 시점에 Streaming STT 세션 종료 이벤트 전송
            # 주의: 마이크는 계속 ON 상태이지만, Streaming STT 세션을 종료하여 큐에 데이터가 누적되지 않도록 함
            print("[DEBUG] GPT-4o 호출 시점: Streaming STT 세션 종료 이벤트 전송 (Clarify GREEN)")
            await broadcast_to("raspi", "stop_streaming_stt", {
                "session_id": session_id,
                "reason": "Clarify GREEN → GPT-4o 최종 답변 생성 시작"
            })
            
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
            print("   모바일에서 TTS 재생 완료 후 audio_playback_completed 이벤트 수신 대기")
            print("=" * 60)
            await wait_for_next_step("모바일로 final_answer 이벤트 전송 완료", "13-10")
            
            # 주의: 문서에 따르면 final_answer 전송 후 service_completed를 보내지 않고,
            # audio_playback_completed (type: "final_answer") 수신 후에만
            # mic_on과 wakeword_start_waiting을 전송합니다.
            # 이는 handle_audio_playback_completed에서 처리됩니다.
            
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
# @sio.on("video_frame")
async def handle_video_frame(sid, data):
    """라즈베리파이 → JPEG binary 수신 후 모션 추정 및 AR 마커 업데이트"""
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown" or not data:
        return

    # --- ① timestamp + frame JSON 파싱 ---
    if isinstance(data, dict):
        timestamp = data.get("timestamp")
        frame_bytes = data.get("frame")
    else:
        # 예전 버전 호환: 바이너리만 온 경우
        timestamp = int(time.time() * 1000)
        frame_bytes = data

    if not frame_bytes:
        print("⚠️ Empty frame data received")
        return

    # --- ② JPEG → OpenCV 이미지 디코딩 ---
    try:
        np_data = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        if frame is None:
            print("⚠️ Failed to decode frame bytes")
            return
        try:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            # frame = cv2.flip(frame, 1)
        except Exception as e:
            print(f"⚠️ Frame rotation error: {e}")
    # 회전 실패 시 원본 프레임으로 계속 진행
    except Exception as e:
        print(f"⚠️ Frame decode error: {e}")
        return

    # timestamp (ms) → YYYYMMDD HH:MM:SS
    # if timestamp:
    #     ts_str = datetime.fromtimestamp(timestamp / 1000).strftime("%Y%m%d %H:%M:%S")
    # else:
    #     ts_str = datetime.now().strftime("%Y%m%d %H:%M:%S")

    # print(f"🖼️ Frame received [{ts_str}] from {sender_device}")  

    #--- ③ 프레임 스트림에 추가 (최근 N개만 유지) ---
    try:
        from app.services.frame_collector import add_frame
        await add_frame(frame)
    except Exception as e:
        print(f"⚠️ 프레임 스트림 추가 오류: {e}")

    # --- ④ 모션 추정 (Optical Flow + RANSAC + Essential) ---
    result = motion_core.process_frame(frame)
    # print(f"[DEBUG] 모션 추정 결과 : {result}")
    if result["status"] not in ("ok", "init"):
        # print("[DEBUG] 모션 추적에 실패했습니다.")
        _, jpeg_bytes = cv2.imencode(".jpg", frame)
        await broadcast_to("pc", "video_frame", jpeg_bytes.tobytes())
        return

    # --- ⑤ AR 마커 업데이트 및 브로드캐스트 (기존 로직 그대로) ---
    if ar_markers:
        # print("[DEBUG] 마커를 계산합니다.")
        updated = []
        for m in ar_markers:
            info = m.get("info", {})
            u = float(info.get("x", 0.0))
            v = float(info.get("y", 0.0))
            # Optical Flow + Essential 기반 업데이트
            u_new, v_new, z_size = motion_core.update_marker_position(u, v)
            # 화면 상에서 크게/작게 보이는 사이즈 반영
            base_size = 10.0
            size_factor = 20.0
            size_px = np.clip(base_size + (z_size * size_factor), 10.0, 100.0)
            updated.append({
                "type": m["type"],
                "idx": m["idx"],
                "info": {
                    "x": round(u_new, 2),
                    "y": round(v_new, 2),
                    "z": round(z_size, 4),
                    "size": round(size_px, 3) if m["type"] == "marker" else m["info"]["size"]
                },
                "color": m["color"],
                "pulseScale": m["pulseScale"],
                "pulseOpacity": m["pulseOpacity"],
                "opacity": m["opacity"]
            })
        ar_markers[:] = updated
        # print(f"arr : {ar_markers}")
        await broadcast_to(["pc", "mobile"], "ar-info", {"markers": ar_markers})

    # --- ⑥ PC로 프레임 전송 (timestamp 포함) ---
    _, jpeg_bytes = cv2.imencode(".jpg", frame)
    await broadcast_to("pc", "video_frame", {
        "timestamp": timestamp,
        "frame": jpeg_bytes.tobytes()
    })

# ========================================
# Raspberry Pi 오디오 프레임 처리
# ========================================
@sio.on("audio_frame")
async def handle_audio_frame(sid, data):
    """라즈베리파이 → binary 오디오 수신 후 웹에 전송"""
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown" or not data:
        return

    # === 클라이언트로 전송 (바이너리 오디오 데이터 그대로 전달) ===
    # print("[DEBUG] 오디오 프레임 수신됨")
    await broadcast_to("pc", "audio_frame", data)

# 모바일에서 '통신 요청중입니다' 음성 종료 이벤트 전달
@sio.on("intent_audio_completed") 
async def handle_start_communication(sid, data):
    """
    오퍼레이터 통신 시작 이벤트
    """
    # print("[DEBUG] intent_audio_completed 이벤트 발생")
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown":
        return

    # === raspi로 "andle_audio_stream" 이벤트 전송 ===
    # await broadcast_to("raspi", "handle_audio_stream", {"start" : True})

# 웹에서 통신 요청 수락 이벤트 전달
@sio.on("accept_communication")
async def accept_communication(sid, data):
    """
    오퍼레이터 통신 시작 이벤트
    AI_Supporter/OPERATOR 실행 중이면 기능을 중지하고 WebRTC 오디오 스트리밍을 시작합니다.
    """
    print("=" * 60)
    print("🔔 [이벤트 수신] accept_communication 이벤트 도착")
    print(f"   SID: {sid[:15]}...")
    print(f"   Sender Device: {device_map.get(sid, 'unknown')}")
    print(f"   Data: {data}")
    print("=" * 60)
    
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown":
        print("⚠️ 알 수 없는 디바이스에서 accept_communication 이벤트 수신")
        print(f"   현재 device_map: {dict(device_map)}")
        print(f"   연결된 디바이스: {list(set(device_map.values()))}")
        print("   ⚠️ 이벤트는 처리하되, device_map에 등록되지 않은 디바이스입니다.")
        # device_map에 등록되지 않아도 이벤트는 처리 (웹에서 전송될 수 있음)

    print("=" * 60)
    print("📞 [통신 요청 수락] AI_Supporter/OPERATOR 기능 중지 및 WebRTC 오디오 스트리밍 시작")
    print("=" * 60)
    
    # 현재 실행 중인 Streaming STT 세션이 있는지 확인
    active_sessions = list(clarify_sessions.keys())
    if active_sessions:
        print("=" * 60)
        print(f"⚠️ [통신 요청 수락] 실행 중인 Streaming STT 세션 발견: {len(active_sessions)}개")
        print(f"   세션 ID: {active_sessions}")
        print("=" * 60)
        
        # 모든 실행 중인 Streaming STT 세션 종료
        for session_id in active_sessions:
            print(f"🛑 [통신 요청 수락] Streaming STT 세션 종료: {session_id}")
            await broadcast_to("raspi", "stop_streaming_stt", {
                "session_id": session_id,
                "reason": "통신 요청 수락으로 인한 중지"
            })
        
        # 세션 정보 정리
        clarify_sessions.clear()
        print("✅ [통신 요청 수락] 모든 Streaming STT 세션 종료 완료")
    else:
        print("ℹ️ [통신 요청 수락] 실행 중인 Streaming STT 세션 없음")
    
    # 주의: 마이크는 하나이며, STT 프로세스가 마이크 장치를 해제한 후 WebRTC가 시작되어야 합니다.
    # 마이크는 항상 ON 상태로 유지되며, STT 세션은 이미 종료되었거나 없을 수 있음
    # handle_audio_stream 이벤트가 브리지 서버를 통해 Python 3.10 프로세스로 전달되어
    # mic.release()가 호출되어 실제 마이크 장치가 해제됩니다.
    print("=" * 60)
    print("📤 [통신 요청 수락] 라즈베리파이로 handle_audio_stream 이벤트 전송")
    print("   Data: {'start': True}")
    print("   목적: WebRTC 오디오 스트리밍을 위해 마이크 장치 물리적 해제")
    print("=" * 60)
    await broadcast_to("raspi", "handle_audio_stream", {"start": True})
    
    # Python 3.10 프로세스가 마이크 장치를 완전히 해제할 시간 확보
    print("⏳ [통신 요청 수락] 마이크 장치 해제 대기 중... (0.3초)")
    await asyncio.sleep(0.3)
    
    print("=" * 60)
    print("✅ [통신 요청 수락] 처리 완료")
    print("   - AI_Supporter/OPERATOR 기능 중지")
    print("   - WebRTC 오디오 스트리밍 시작 준비 완료")
    print("=" * 60)

# 웹에서 통신 종료 이벤트 전달
@sio.on("communication_close")
async def communication_close(sid, data):
    """
    오퍼레이터 통신 종료 이벤트
    """
    print("=" * 60)
    print("🔔 [이벤트 수신] communication_close 이벤트 도착")
    print(f"   SID: {sid[:15]}...")
    print(f"   Sender Device: {device_map.get(sid, 'unknown')}")
    print(f"   Data: {data}")
    print("=" * 60)
    
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown":
        print("⚠️ 알 수 없는 디바이스에서 communication_close 이벤트 수신 - 무시")
        return

    print("=" * 60)
    print("📞 [통신 종료] WebRTC 오디오 스트리밍 중지 및 STT 목적 음성 수집 재개")
    print("=" * 60)
    
    # WebRTC 오디오 스트리밍 목적 음성 수집 중지
    # handle_audio_stream 이벤트가 브리지 서버를 통해 Python 3.10 프로세스로 전달되어
    # mic.acquire()가 호출되어 실제 마이크 장치를 재점유합니다.
    print("=" * 60)
    print("📤 [통신 종료] 라즈베리파이로 handle_audio_stream 이벤트 전송")
    print("   Data: {'start': False}")
    print("   목적: STT/Wakeword 프로세스가 마이크 장치를 물리적 재점유")
    print("=" * 60)
    await broadcast_to("raspi", "handle_audio_stream", {"start": False})
    # 마커 데이터 초기화
    global ar_markers
    ar_markers = []
    # WebRTC 프로세스가 마이크를 완전히 해제하고 Python 3.10 프로세스가 마이크를 재점유할 시간 확보
    print("⏳ [통신 종료] 마이크 장치 재점유 대기 중... (0.3초)")
    await asyncio.sleep(0.3)
    
    # 주의: 마이크는 handle_audio_stream({"start": False})에서 이미 재점유되어 ON 상태임
    # 마이크는 항상 ON 상태로 유지되므로 별도의 mic_on 이벤트 불필요
    
    # Wakeword 감지 대기 시작
    print("=" * 60)
    print("📤 [통신 종료] 라즈베리파이로 wakeword_start_waiting 이벤트 전송")
    print("   목적: Wakeword 감지 대기 상태로 복귀")
    print("=" * 60)
    await broadcast_to("raspi", "wakeword_start_waiting", {})
    
    print("=" * 60)
    print("📤 [통신 종료] 기기 탐지 작업 시작")
    print("=" * 60)
    await start_device_detector_task()
    
    print("✅ 통신 종료 처리 완료: WebRTC 오디오 스트리밍 중지, STT 목적 음성 수집 재개, Wakeword 감지 대기 시작, 기기 탐지 시작")

    print("=" * 60)
    print("✅ [통신 종료] 처리 완료")
    print("   - WebRTC 오디오 스트리밍 중지")
    print("   - STT 목적 음성 수집 재개")
    print("   - Wakeword 감지 대기 시작")
    print("   - 기기 탐지 시작")
    print("=" * 60)


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
ar_markers = []  # [{ "type": str, "idx": int, "info": { "x": float, "y": float, "size": float } }, ...]

async def handle_ar_marker(sid, data):
    """
    AR 마커 생성:
    - x, y: Optical Flow 기반 화면 좌표
    - size: Essential Matrix 기반 z-scale
    """
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown":
        return

    u = float(data.get("marker_x"))
    v = float(data.get("marker_y"))
    # print(f"[DEBUG] 마커 입력이 들어왔습니다. : [{u}, {v}]")
    # 현재 프레임의 위치를 기준점으로 한다.
    # 이후 motion_core.process_frame()에서 Optical Flow로 자동 갱신됨
    u_new, v_new, z_scale = motion_core.update_marker_position(u, v)
    # z_scale = Essential Matrix에서 얻은 상대 깊이 변화량
    size_px = motion_core.compute_marker_size(z_scale)
    marker = {
        "type": "marker",
        "idx": len(ar_markers) + 1,
        "info": {
            "x": u_new,
            "y": v_new,
            "size": size_px
        },
        "color": data.get("color"),
        "pulseScale": data.get("pulseScale", 1.0),
        "pulseOpacity": data.get("pulseOpacity", 1.0),
        "opacity": data.get("opacity", 1.0)
    }
    ar_markers.append(marker)
    # print(f"[DEBUG] arr : {ar_markers}")
    # await sio.emit("ar-info", {"markers": ar_markers}, to=sid)
    await broadcast_to(["pc", "mobile"], "ar-info", {"markers": ar_markers})

async def delete_marker(sid, data):
    """
    전달받은 idx에 해당하는 AR 마커 삭제
    """
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown":
        return

    target_idx = data.get("idx")
    if target_idx is None:
        print("⚠️ delete_marker: idx 값이 없습니다.")
        return

    global ar_markers
    # 기존 리스트에서 target_idx가 아닌 것만 남긴다
    ar_markers = [m for m in ar_markers if m.get("idx") != target_idx]


    # 삭제 이후 남아있는 모든 마커 idx를 다시 1부터 정렬할 필요가 있다면:
    for i, marker in enumerate(ar_markers, start=1):
        marker["idx"] = i
    
    # 전송을 하긴 하는데, 없어도 될듯?
    await broadcast_to(["pc", "mobile"], "ar-info", {"markers": ar_markers})
