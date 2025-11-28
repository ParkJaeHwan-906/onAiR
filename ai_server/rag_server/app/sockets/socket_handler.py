# app/sockets/socket_handler.py
"""
FastAPI 서버용 Socket.IO 이벤트 핸들러

설계 요구사항:
1. 라즈베리파이로부터 STT 텍스트 직접 수신 (WebSocket)
"""
import socketio
import cv2
import numpy as np
import asyncio
import os
import time
from typing import Dict, Any, Optional
from app.services.intent_service import classify_intent
from app.services.generator import generate_cv_detection_notification
from app.services.tts_service import text_to_speech
from app.ar import motion_core
from app.services.yolo_overlay import get_latest_yolo_result
from app.services.cv_service import run_anomaly_detection
from app.services.final_guide import generate_final_guide
from app.services.gesture_state import GestureManager

# 서비스 종료 버튼 좌표 (left=1800, top=90, right=1950, bottom=240)
SERVICE_END_BUTTON_RECT = (1800, 90, 1950, 240)

# Gesture 인식 상태 관리 (클래스로 캡슐화)
gesture_manager = GestureManager(SERVICE_END_BUTTON_RECT)

# settings는 wait_for_next_step에서 사용되므로 반드시 import 필요
from app.core.config import settings

try:
    import google.generativeai as genai
    genai_available = True
    if settings.GMS_API_KEY:
        genai.configure(api_key=settings.GMS_API_KEY)
except Exception:
    genai = None
    genai_available = False

# CV 탐지 결과 임시 저장 (audio_playback_completed에서 사용)
_pending_cv_detection: Optional[Dict[str, Any]] = None

# Socket.IO 서버 인스턴스 (main.py에서 생성)
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # 모든 Origin 허용
    logger=False,  # 로거 비활성화
)

# 디바이스 타입 저장 (세션 ID → 디바이스 타입)
device_map: Dict[str, str] = {}  # { sid: "raspi" | "mobile" | "pc" }


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
        return
    
    # 이벤트 핸들러 등록 (데코레이터 대신 직접 등록)
    sio.on("connect")(handle_connect)
    sio.on("disconnect")(handle_disconnect)
    sio.on("register_device")(handle_register_device)
    sio.on("stt_result")(handle_stt_result)
    sio.on("wakeword_detected")(handle_wakeword_detected)                # 라즈베리파이에서 Wakeword 감지 이벤트 수신
    sio.on("wakeword_waiting_ready")(handle_wakeword_waiting_ready)      # 라즈베리파이에서 Wakeword 대기 준비 완료 이벤트 수신 (YOLO 서버 API 요청 트리거)
    sio.on("wakeword_audio_completed")(handle_wakeword_audio_completed)  # 모바일에서 음성 파일 재생 완료 이벤트 수신
    sio.on("intent_audio_completed")(handle_intent_audio_completed)      # 모바일에서 Intent 음성 파일 재생 완료 이벤트 수신 (AI_SUPPORTER용)
    sio.on("audio_playback_completed")(handle_audio_playback_completed)  # 모바일에서 오디오 재생 완료 이벤트 수신
    sio.on("control_raspi")(handle_control_raspi)                        # 모바일에서 라즈베리파이 제어 명령
    sio.on("video_frame")(handle_video_frame)
    sio.on("audio_frame")(handle_audio_frame)  
    sio.on("ar-marker")(handle_ar_marker)
    sio.on("delete-marker")(delete_marker)
    sio.on("active_mediapipe")(handle_active_mediapipe)
    
# === 타입별 브로드캐스트 (안전 버전) ===
async def broadcast_to(device_types, event: str, payload: dict):
    """
    특정 디바이스 타입(하나 또는 여러 개)에 이벤트 전송
    - device_types: 문자열('raspi') 또는 리스트(['raspi', 'mobile'])
    - payload: dict 형태의 전송 데이터
    """
    if isinstance(device_types, str):
        device_types = [device_types]

    # dictionary snapshot으로 안전한 iteration
    targets = list(device_map.items())
    
    # 연결된 디바이스 확인
    available_devices = [dev for sid, dev in targets if dev in device_types]
    if not available_devices:
        return
    
    for sid, dev in targets:
        if dev in device_types:
            try:
                await sio.emit(event, payload, to=sid)
            except Exception as e:
                # 연결 끊긴 클라이언트가 있을 수 있으므로 예외 무시하고 다음으로 진행
                import traceback
                traceback.print_exc()
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
        if sio:
            await sio.emit("server_message", {"msg": "Connected"}, to=sid)
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False


async def handle_disconnect(sid):
    """클라이언트 연결 해제"""
    if sid in device_map:
        del device_map[sid]


async def handle_register_device(sid, data):
    """디바이스 등록"""
    device = data.get("device", "unknown")
    device_map[sid] = device
    logger.info(f"디바이스 등록됨 : {}", device)
    logger.info(f"{device_map}")
    if sio:
        await sio.save_session(sid, {"device": device})
        await sio.emit("server_message", {"msg": f"Device '{device}' registered"}, to=sid)

# ========================================
# 공통 시작 파이프라인(버튼 클릭으로 시작/wakeword 감지로 시작작)
# ========================================
async def trigger_start_pipeline(source: str):
    """
    wakeword 또는 gesture start 클릭 시 동일한 시작 파이프라인 실행
    """
    print(f"Start pipeline triggered by: {source}")


# ========================================
# Wakeword 이벤트 핸들러
# ========================================

async def handle_wakeword_detected(sid, data):
    """
    라즈베리파이로부터 Wakeword 감지 이벤트 수신
    모바일로 이벤트를 전송하여 음성 파일 재생 시작
    """
    print("🎤 Wakeword 감지됨")
    sender_device = device_map.get(sid, "unknown")
    
    # 라즈베리파이에서만 받음
    if sender_device != "raspi":
        print(f"⚠️ Wakeword 감지 이벤트는 라즈베리파이에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    detected = data.get("detected", False)

    print("=" * 80)
    print("🎤 [Wakeword 감지] 라즈베리파이로부터 wakeword_detected 이벤트 수신")
    print(f"   세션 ID: {sid}")
    print("=" * 80)
    
    await wait_for_next_step("Wakeword 감지 이벤트 수신 완료", "2-1")
    
    # 모바일 연결 상태 확인
    mobile_sids = [s for s, d in device_map.items() if d == "mobile"]
    if not mobile_sids:
        print("⚠️ 모바일 디바이스가 연결되어 있지 않습니다.")
        return
    
    print(f"📤 모바일로 wakeword_detected 이벤트 전송 시작 (연결된 모바일: {len(mobile_sids)}개)")
    
    # 모바일로 Wakeword 감지 이벤트 전송 (음성 파일 재생 시작)
    await broadcast_to("mobile", "wakeword_detected", {
        "detected": detected
    })
    
    print("✅ 모바일로 wakeword_detected 이벤트 전송 완료")
    await wait_for_next_step("모바일로 Wakeword 감지 이벤트 전송 완료", "2-1-1")
    
    # ⚠️ 주의: wakeword_audio_completed는 모바일에서 오디오 재생 완료 후 
    # handle_wakeword_audio_completed 함수에서 라즈베리파이로 전달됩니다.


async def handle_wakeword_waiting_ready(sid, data):
    """
    라즈베리파이로부터 Wakeword 대기 준비 완료 이벤트 수신
    YOLO 서버로 API 요청을 보내기 위한 트리거
    """
    sender_device = device_map.get(sid, "unknown")
    
    # 라즈베리파이에서만 받음
    if sender_device != "raspi":
        print(f"⚠️ Wakeword 대기 준비 완료 이벤트는 라즈베리파이에서만 받을 수 있습니다. 수신자: {sender_device}")
        return

async def handle_wakeword_audio_completed(sid, data):
    """
    모바일로부터 음성 파일 재생 완료 이벤트 수신
    라즈베리파이로 전달하여 다음 단계 진행
    """
    sender_device = device_map.get(sid, "unknown")
    
    # 모바일에서만 받음
    if sender_device != "mobile":
        print(f"⚠️ 음성 파일 재생 완료 이벤트는 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    await wait_for_next_step("모바일 음성 파일 재생 완료 이벤트 수신 완료", "2-2")
    
    # 라즈베리파이로 wakeword_audio_completed 전달 (다음 단계 진행)
    raspi_sids = [s for s, d in device_map.items() if d == "raspi"]
    if raspi_sids:
        await broadcast_to("raspi", "wakeword_audio_completed", {
            "timestamp": None
        })
        await wait_for_next_step("라즈베리파이로 wakeword_audio_completed 전달 완료", "2-2-1")
    else:
        print("⚠️ 라즈베리파이 디바이스가 연결되어 있지 않습니다.")


async def handle_intent_audio_completed(sid, data):
    """
    모바일로부터 Intent 음성 파일 재생 완료 이벤트 수신
    AI_SUPPORTER인 경우 CV 로직 실행
    """
    global _pending_cv_detection
    
    sender_device = device_map.get(sid, "unknown")

    # 모바일에서만 받음
    if sender_device != "mobile":
        print(f"⚠️ Intent 음성 파일 재생 완료 이벤트는 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    intent = data.get("intent", "").upper()

    # ---------------------------------------------------------
    # AI_SUPPORTER → CV 분석 실행
    # ---------------------------------------------------------
    if intent == "AI_SUPPORTER":
        print("=" * 80)
        print("🔍 [CV 탐지 시작] AI_SUPPORTER Intent 수신 - CV 이상 탐지 실행")
        print("=" * 80)
        try:
            print("📡 YOLO 서비스로 이상 탐지 요청 전송 중...")
            cv_raw = await run_anomaly_detection()
            print("✅ YOLO 서비스 응답 수신 완료")
            print(f"   응답 데이터: {cv_raw}")

            detected = cv_raw.get("detected", False)
            has_anomaly = cv_raw.get("has_anomaly", False)
            modules_detected = cv_raw.get("modules_detected", False)  # ★ 모듈 탐지 여부
            device_type = cv_raw.get("device_type", "unknown")
            modules = cv_raw.get("modules", [])
            anomalies = cv_raw.get("anomalies", {})     # ★ 이미 정제됨
            messages = cv_raw.get("messages", [])       # ★ 이미 정제됨
            
            print("=" * 80)
            print(f"📊 [CV 탐지 결과 분석]")
            print(f"   detected: {detected}")
            print(f"   has_anomaly: {has_anomaly}")
            print(f"   modules_detected: {modules_detected}")  # ★ 추가
            print(f"   device_type: {device_type}")
            print(f"   modules 개수: {len(modules)}")
            print(f"   anomalies 개수: {len(anomalies)}")
            print(f"   anomalies 상세: {anomalies}")
            print(f"   messages: {messages}")
            print("=" * 80)

            # 최종 구조
            # ★ message는 final_guide.py에서 문자열로 사용되므로 messages 리스트를 문자열로 변환
            # messages가 비어있으면 빈 문자열, 아니면 첫 번째 메시지 사용
            message_str = messages[0] if messages and isinstance(messages, list) else (messages if isinstance(messages, str) else "")
            
            cv_result = {
                "detected": detected,
                "device_type": device_type,
                "modules": modules,
                "anomalies": anomalies,
                "message": message_str,  # ★ 문자열로 통일
                "messages": messages,    # ★ 리스트도 보존 (필요시 사용)
                "modules_detected": modules_detected
            }

            # -------------------------
            # 1) 탐지 실패 (모듈 탐지 실패 / AHU 아님 / YOLO 없음 / 프레임 없음 등)
            # ★ detected = modules_detected이므로 detected=False는 모듈 탐지 실패를 의미
            # -------------------------
            if not detected:
                print("=" * 80)
                print("❌ [CV 탐지 실패] detected=False (모듈 탐지 실패 또는 시스템 오류)")
                print(f"   device_type: {device_type}")
                print(f"   modules_detected: {modules_detected}")
                print(f"   message: {cv_raw.get('message', 'N/A')}")
                print("=" * 80)
                _pending_cv_detection = cv_result
                await broadcast_to("mobile", "cv_detection_failed", {
                    "message": "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다."
                })
                return

            # -------------------------
            # 2) 정상 (모듈 탐지 OK + 이상 없음)
            # ★ detected = modules_detected = True인 경우
            # -------------------------
            if detected and not has_anomaly:
                print("=" * 80)
                print("✅ [CV 탐지 정상] detected=True, modules_detected=True, has_anomaly=False")
                print(f"   device_type: {device_type}")
                print(f"   anomalies 개수: {len(anomalies)}")
                print("=" * 80)
                _pending_cv_detection = cv_result
                await broadcast_to("mobile", "cv_detection_normal", {
                    "message": "탐지 결과 정상입니다. 오퍼레이터와의 통신을 통해 문제를 해결하겠습니다."
                })
                return

            # -------------------------
            # 3) 이상 (anomaly)
            # -------------------------
            print("=" * 80)
            print("🚨 [CV 탐지 이상] detected=True, has_anomaly=True")
            print(f"   device_type: {device_type}")
            print(f"   anomalies: {anomalies}")
            print(f"   messages: {messages}")
            print("=" * 80)
            await wait_for_next_step("CV 모델 오류 탐지 성공", "9")

            # 알림 메시지 생성
            notification_text = generate_cv_detection_notification(device_type, anomalies)

            # TTS 변환
            try:
                tts_res = text_to_speech(notification_text)
                audio_data = tts_res.get("audio_content")
                audio_type = tts_res.get("mime_type")
            except Exception as e:
                print(f"⚠️ 탐지 알림 TTS 변환 실패: {e}")
                audio_data = None
                audio_type = None

            # pending 저장
            _pending_cv_detection = cv_result

            # anomaly payload
            payload = {
                "message": notification_text,
                "audio_content": audio_data,
                "audio_encoding": audio_type,
                "cv_detection_result": cv_result
            }

            # 모바일로 anomaly 전송
            await broadcast_to("mobile", "cv_detection_anomaly", payload)
            # await broadcast_to(["mobile", "pc"], "cv_detection_anomaly", payload)

            # ⚠️ 주의: cv_detection_success는 generate_final_guide에서 전송됨 (중복 방지)

        except Exception as e:
            print(f"❌ CV 모델 실행 오류: {e}")
            import traceback
            traceback.print_exc()

            await broadcast_to("mobile", "cv_detection_failed", {
                "message": "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다."
            })
            return

    # ---------------------------------------------------------
    # OPERATOR → WebRTC 오디오 송출 대기
    # ---------------------------------------------------------
    elif intent == "OPERATOR":
        pass



async def handle_audio_playback_completed(sid, data):
    """
    모바일로부터 오디오 재생 완료 이벤트 수신
    - type="cv_detection_failed": CV 탐지 실패 음성 파일 재생 완료 → WebRTC 오디오 스트리밍 대기 상태
    - type="cv_detection_normal": CV 탐지 정상 음성 파일 재생 완료 → WebRTC 오디오 스트리밍 대기 상태
    - type="cv_detection_anomaly": CV 탐지 알림 TTS 재생 완료 → 전체 정비 가이드 생성 시작
    - type="sections_completed": 섹션별 TTS 재생 완료 → 서비스 종료 버튼 활성화 요청
    """
    # CV 탐지 관련 오디오 재생 완료 처리
    # _pending_cv_detection 전역 변수로 상태 판단 (type 파라미터 불필요)
    global _pending_cv_detection
    
    sender_device = device_map.get(sid, "unknown")
    
    # 모바일에서만 받음
    if sender_device != "mobile":
        print(f"⚠️ 오디오 재생 완료 이벤트는 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    audio_type = data.get("type", "")
    
    # CV 탐지 결과가 있는 경우 (cv_detection_failed, cv_detection_normal, cv_detection_anomaly)
    if _pending_cv_detection:
        if audio_type == "cv_detection_failed" or audio_type == "cv_detection_normal":
            # CV 탐지 실패/정상 음성 파일 재생 완료 → WebRTC 오디오 스트리밍 대기 상태
            _pending_cv_detection = None
        elif audio_type == "cv_detection_anomaly":
            # CV 탐지 알림 TTS 재생 완료 → 전체 정비 가이드 생성 시작
            # _pending_cv_detection은 line 463에서 이미 None 체크 완료
            device_type = _pending_cv_detection["device_type"]
            modules = _pending_cv_detection["modules"]
            anomalies = _pending_cv_detection["anomalies"]
            # cv_result는 generate_final_guide에서 message만 사용하므로 message만 전달
            # message는 문자열로 저장되어 있음
            cv_result = {"message": _pending_cv_detection.get("message", "")}
            
            print("=" * 80)
            print("📚 [GPT 답변 생성 시작] CV 탐지 이상 → 전체 정비 가이드 생성")
            print(f"   device_type: {device_type}")
            print(f"   anomalies: {anomalies}")
            print("=" * 80)
            
            # 전체 정비 가이드 생성 및 전송 (서비스 사용)
            await generate_final_guide(device_type, modules, anomalies, cv_result, broadcast_to)
            _pending_cv_detection = None
    
    elif audio_type == "sections_completed":
        # AI_Supporter 섹션별 TTS 재생 완료 → 서비스 종료 버튼 활성화 요청
        print("=" * 80)
        print("✅ [섹션별 TTS 재생 완료] 서비스 종료 버튼 활성화 요청")
        print("=" * 80)
        
        await broadcast_to("mobile", "enable_service_end_button", {
            "button_rect": {
                "left": 1800,
                "top": 90,
                "right": 1950,
                "bottom": 240
            },
            "center": {
                "x": 1875,
                "y": 165
            }
        })

        await broadcast_to("raspi", "audio_playback_completed", {})

        await wait_for_next_step("서비스 종료 버튼 활성화 요청 전송 완료", "14-1")


# ========================================
# STT 이벤트 핸들러 (버퍼링)
# ========================================

async def handle_stt_result(sid, data):
    """
    라즈베리파이로부터 STT 결과 수신 (버퍼링)
    
    설계 요구사항:
    - 버퍼링 STT: type="final" → Gemini-Flash로 Intent 분류 → 모바일 전송
    """
    sender_device = device_map.get(sid, "unknown")
    
    # 라즈베리파이에서만 받음
    if sender_device != "raspi":
        print(f"⚠️ STT 결과는 라즈베리파이에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    stt_type = data.get("type", "unknown")
    stt_text = data.get("text", "").strip()
    confidence = data.get("confidence")
    
    await wait_for_next_step("STT 결과 수신 완료", "6")
    
    # 버퍼링 STT (type="final")
    if stt_type == "final":
        # STT 텍스트가 비어있으면 처리 불가
        if not stt_text:
            print("⚠️ STT 텍스트가 비어있습니다. Intent 분류를 수행할 수 없습니다.")
            return
        
        # 1. 먼저 모바일로 SSE 연결 시작 요청 전송
        try:
            await broadcast_to("mobile", "start_sse_connection", {
                "text": stt_text,
                "timestamp": None
            })
            await wait_for_next_step("SSE 연결 시작 요청 전송 완료", "6-1")
        except Exception as e:
            print(f"⚠️ SSE 연결 시작 요청 전송 실패: {e}")
        
        # 2. Gemini-Flash로 Intent 분류 및 모바일로 전송
        try:
            intent_result = classify_intent(stt_text)
            intent = intent_result.get("intent", "AI_SUPPORTER")
            
            await wait_for_next_step("Intent 분류 완료", "7")
            
            # 모바일로 Intent 결과 전송
            await broadcast_to("mobile", "intent_result", {
                "text": stt_text,
                "intent": intent,
                "confidence": intent_result.get("confidence", 0.5),
                "reasoning": intent_result.get("reasoning", ""),
                "stt_confidence": confidence
            })
            
            await wait_for_next_step("모바일로 intent_result 이벤트 전송 완료", "8")
            
            # 버퍼링 STT 세션 종료 이벤트 전송
            await broadcast_to("raspi", "stop_buffered_stt", {
                "reason": "버퍼링 STT 결과 전송 완료, Intent 분류 진행"
            })
            await wait_for_next_step("버퍼링 STT 세션 종료 이벤트 전송 완료", "8-0")
                    
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


# ========================================
# Raspberry Pi 비디오 프레임 처리
# ========================================
async def handle_video_frame(sid, data):
    """라즈베리파이 → JPEG binary 수신 후 모션 추정 및 AR 마커 업데이트"""
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown" or not data:
        return

    # timestamp + frame JSON 파싱
    if isinstance(data, dict):
        timestamp = data.get("timestamp")
        frame_bytes = data.get("frame")
    else:
        timestamp = int(time.time() * 1000)
        frame_bytes = data

    if not frame_bytes:
        print("⚠️ Empty frame data received")
        return

    # JPEG → OpenCV 이미지 디코딩
    try:
        np_data = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        if frame is None:
            print("⚠️ Failed to decode frame bytes")
            return
        try:
            # frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            frame = cv2.flip(frame, -1)
        except Exception as e:
            print(f"⚠️ Frame rotation error: {e}")
    except Exception as e:
        print(f"⚠️ Frame decode error: {e}")
        return

    # 프레임 스트림에 추가 (최근 N개만 유지)
    try:
        from app.services.frame_collector import add_frame
        await add_frame(frame, timestamp)
    except Exception as e:
        print(f"⚠️ 프레임 스트림 추가 오류: {e}")

    # 모션 추정 (Optical Flow + RANSAC + Essential)
    result = motion_core.process_frame(frame)
    if result["status"] not in ("ok", "init"):
        _, jpeg_bytes = cv2.imencode(".jpg", frame)
        await broadcast_to('pc', "video_frame", {
            "timestamp": timestamp,
            "frame": jpeg_bytes.tobytes()
        })
        await broadcast_to('mobile', "video_frame", jpeg_bytes.tobytes())
        return

    # AR 마커 업데이트 및 브로드캐스트
    if ar_markers:
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
                    "size": round(size_px, 3) if m["type"] == "marker" else m["info"]["size"]
                },
                "color": m["color"],
                "pulseScale": m["pulseScale"],
                "pulseOpacity": m["pulseOpacity"],
                "opacity": m["opacity"]
            })
        ar_markers[:] = updated
        await broadcast_to(['pc', 'mobile'], "ar-info", {"markers": ar_markers})

    # ================================
    # 제스처로 서비스 종료 버튼 클릭 감지
    # ================================
    await gesture_manager.handle_frame(
    frame,
    on_gesture_service_start,
    on_gesture_service_end
    )

    # ================================
    # 이후 PC/모바일로 프레임 전송
    # ================================
    # PC로 프레임 전송 (timestamp 포함)
    _, jpeg_bytes = cv2.imencode(".jpg", frame)
    await broadcast_to('pc', "video_frame", {
        "timestamp": timestamp,
        "frame": jpeg_bytes.tobytes()
    })
    await broadcast_to('mobile', "video_frame", jpeg_bytes.tobytes())
    
    try:
        yolo_res = await get_latest_yolo_result()
        if yolo_res:
            frame_ts = yolo_res.get("frame_ts")
            if frame_ts and abs(frame_ts - timestamp) <= 200:
                payload = {
                    "timestamp": frame_ts,
                    "boxes": yolo_res.get("boxes", []),
                }
                await broadcast_to(['pc', 'mobile'], "video_overlay", payload)
    except Exception as e:
        print(f"⚠️ YOLO overlay 전송 오류: {e}")


# ========================================
# mobile로부터 mediapipe on 이벤트 받으면 켜기
# ========================================
async def handle_active_mediapipe(sid, data):
    sender_device = device_map.get(sid, "unknown")
    if sender_device != "mobile":
        return

    rect=data.get("rect")
    if not rect:
        print("active_mediapipe: rect 없음")
        return

    # mediapipe 켜기
    gesture_manager.enabled= True
    gesture_manager.button_rect= (
        rect['left'],
        rect['top'],
        rect['right'],
        rect['bottom']
    )

    # START 모드 요청
    if not gesture_manager.waiting_for_start and not gesture_manager.waiting_for_end:

        gesture_manager.waiting_for_start= True
        print("Gesture mode: waiting for start")
        return

    # END 모드 요청
    if gesture_manager.waiting_for_start and not gesture_manager.waiting_for_end:
        gesture_manager.waiting_for_start= False
        gesture_manager.waiting_for_end= True
        print("Gesture mode: waiting for end")
        return

    # 그 외: 다시 초기화(비활성화일 때처럼)
    gesture_manager.waiting_for_start= True
    gesture_manager.waiting_for_end= False
    print("Gesture mode reset-> waiting for start")

# ========================================
# mediapipe에서 시작 버튼 눌렸을 때 FastAPI 반응(gesture start 콜백)
# ========================================
async def on_gesture_service_start():
    print("Gesture START detected")

    # 모바일로 시작 버튼 클릭 알림
    await broadcast_to("mobile", "service_start_clicked", {})

    # wakeword 없이도 시작 로직 호출- wakeword 이후 흐름을 그대로 실행하게 하는 진입점
    await trigger_start_pipeline("gesture")

# ========================================
# mediapipe에서 종료 버튼 눌렸을 때 FastAPI 반응(gesture end 콜백)
# ========================================
async def on_gesture_service_end():
    print("Gesture END detected")

    # 모바일로 서비스 종료 버튼 클릭 알림
    await broadcast_to("mobile", "service_end_clicked", {})
    
    # 2. FastAPI 내부 상태 즉시 초기화 (모바일 응답 대기 없이)
    global _pending_cv_detection
    
    # 제스처 인식 비활성화 (필수 - 다음 서비스 시작 전까지 인식 방지)
    gesture_manager.enabled = False
    
    # CV 탐지 결과 초기화 (필수 - 다음 서비스 시작 시 이전 값 방지)
    _pending_cv_detection = None
    
    # 3. 라즈베리파이에 서비스 종료 알림 (내부 초기화 로직 자동 실행)
    await broadcast_to("raspi", "audio_playback_completed", {})
    
    print("✅ 서비스 종료 처리 완료 - 초기 상태로 복귀")
# ========================================
# Raspberry Pi 오디오 프레임 처리
# ========================================
@sio.on("audio_frame")
async def handle_audio_frame(sid, data):
    """라즈베리파이 → binary 오디오 수신 후 웹에 전송"""
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown" or not data:
        return

    await broadcast_to("pc", "audio_frame", data)

# 웹에서 통신 요청 수락 이벤트 전달
@sio.on("accept_communication")
async def accept_communication(sid, data):
    """
    오퍼레이터 통신 시작 이벤트
    AI_Supporter/OPERATOR 실행 중이면 기능을 중지하고 WebRTC 오디오 스트리밍을 시작합니다.
    """
    logger.info("오퍼레이터 통신 시작됨")
    logger.info(f"{device_map}")
    global ar_markers
    ar_markers.clear()

    await broadcast_to("raspi", "handle_audio_stream", {"start": True})
    await asyncio.sleep(0.3)

    description = {
        "type": "description",
        "idx": -1,
        "info": {
            "x": 0.0,
            "y": 0.0,
            "size": 10
        },
        "color": None,
        "pulseScale": None,
        "pulseOpacity": None,
        "opacity": None
    }
    ar_markers.append(description)

# 웹에서 통신 종료 이벤트 전달
@sio.on("communication_close")
async def communication_close(sid, data):
    """
    오퍼레이터 통신 종료 이벤트
    """
    logger.info("오퍼레이터 통신을 종료합니다.")
    logger.info(f"{device_map}")
    global ar_markers
    
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown":
        return

    await broadcast_to("raspi", "handle_audio_stream", {"start": False})
    ar_markers.clear()
    await asyncio.sleep(0.3)
    
    await broadcast_to("mobile", "communication_close", {})
    await broadcast_to("raspi", "audio_playback_completed", {})


# ========================================
# 라즈베리파이 제어 이벤트 (모바일 → 라즈베리파이)
# ========================================

async def handle_control_raspi(sid, data):
    """
    모바일에서 전송된 라즈베리파이 제어 명령을 수신하여 라즈베리파이로 전달
    """
    sender_device = device_map.get(sid, "unknown")
    
    # 모바일에서만 받음
    if sender_device != "mobile":
        print(f"⚠️ 라즈베리파이 제어 명령은 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    await broadcast_to("raspi", "control_raspi", data)

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
    u_new, v_new, z_scale = motion_core.update_marker_position(u, v)
    size_px = motion_core.compute_marker_size(z_scale)
    next_idx = sum(1 for m in ar_markers if m.get("type") == "marker") + 1
    marker = {
        "type": "marker",
        "idx": next_idx,
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
    await broadcast_to(['pc', 'mobile'], "ar-info", {"markers": ar_markers})

async def delete_marker(sid, data):
    """
    전달받은 idx에 해당하는 AR 마커 삭제
    """
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown":
        return

    target_idx = data.get("idx")
    if target_idx is None:
        return

    global ar_markers
    ar_markers = [m for m in ar_markers if m.get("idx") != target_idx]

    # 삭제 이후 남아있는 모든 마커 idx를 다시 1부터 정렬
    idx = 1
    for marker in ar_markers:
        if marker.get("type") == "marker":
            marker["idx"] = idx
            idx += 1
    
    await broadcast_to(['pc', 'mobile'], "ar-info", {"markers": ar_markers})

    