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
# SERVICE_END_BUTTON_RECT = (1800, 90, 1950, 240)
SERVICE_END_BUTTON_RECT = (1710, 45, 1860, 195)

# Gesture 인식 상태 관리 (클래스로 캡슐화)
# gesture_manager = GestureManager(SERVICE_END_BUTTON_RECT)

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

_pending_final_guide: Optional[Dict[str, Any]] = None
_final_guide_lock = asyncio.Lock()

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
    print("=" * 80)
    print("🔧 [Socket.IO] init_socketio() 호출 시작")
    print("=" * 80)
    
    if sio is None:
        print("❌ [Socket.IO] sio가 None입니다. 이벤트 핸들러를 등록할 수 없습니다.")
        return
    
    print("✅ [Socket.IO] sio 인스턴스 확인 완료")
    
    # 이벤트 핸들러 등록 (데코레이터 대신 직접 등록)
    print("📝 [Socket.IO] 이벤트 핸들러 등록 시작...")
    sio.on("connect")(handle_connect)
    print("   ✅ connect 핸들러 등록 완료")
    sio.on("disconnect")(handle_disconnect)
    print("   ✅ disconnect 핸들러 등록 완료")
    sio.on("register_device")(handle_register_device)
    print("   ✅ register_device 핸들러 등록 완료")
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
    sio.on("wakeword_force")(handle_wakeword_force)
    # sio.on("active_mediapipe")(handle_active_mediapipe)
    print("   ✅ active_mediapipe 핸들러 등록 완료")
    print("=" * 80)
    print("✅ [Socket.IO] 모든 이벤트 핸들러 등록 완료")
    print("=" * 80)
    

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
    print("=" * 80)
    print(f"🔌 [Connection] 클라이언트 연결: sid={sid}")
    print(f"   IP: {environ.get('REMOTE_ADDR', 'unknown')}")
    print(f"   User-Agent: {environ.get('HTTP_USER_AGENT', 'unknown')}")
    print(f"   현재 등록된 디바이스: {device_map}")
    print("=" * 80)
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
    print("=" * 80)
    print(f"🔌 [Connection] 클라이언트 연결 해제: sid={sid}")
    if sid in device_map:
        device = device_map[sid]
        print(f"   해제된 디바이스: {device}")
        del device_map[sid]
    print(f"   남은 디바이스: {device_map}")
    print("=" * 80)


async def handle_register_device(sid, data):
    """디바이스 등록"""
    device = data.get("device", "unknown")
    device_map[sid] = device
    print(f"📝 [Device Registration] 디바이스 등록: {device}, sid: {sid}")
    print(f"   현재 등록된 디바이스: {device_map}")
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
    mobile_sids = [s for s, d in device_map.items() if d == "mobile" or d == "mobile2"]
    if not mobile_sids:
        print("⚠️ 모바일 디바이스가 연결되어 있지 않습니다.")
        return
    
    print(f"📤 모바일로 wakeword_detected 이벤트 전송 시작 (연결된 모바일: {len(mobile_sids)}개)")
    
    # 모바일로 Wakeword 감지 이벤트 전송 (음성 파일 재생 시작)
    await broadcast_to(["mobile", "mobile2"], "wakeword_detected", {
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
    if sender_device != "mobile" and sender_device != "mobile2":
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
    global _pending_final_guide
    
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
                await broadcast_to(["mobile", "mobile2"], "cv_detection_failed", {
                    "message": "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다."
                })
                return

            # 장비 고정을 위해 modules 의 dic 에서 label 과 has_anomaly 만 우선 추출
            filtered = [
                {
                    "label": m.get("label"),
                    "has_anomaly": m.get("has_anomaly")
                }
                for m in modules
            ]
            # 정상 상태인 항목에 대해서 우선 순위를 부여
            # sorted_filtered = sorted(filtered, key=lambda x: x["has_anomaly"])
            sorted_filtered = sorted(filtered, key=lambda x: x["has_anomaly"], reverse=True)

            # 시연용 fan 으로 탐지 되어있을 때는 반드시 오류 탐지로 이동할 수 있도록
            if device_type == "AHU" and sorted_filtered[0]["label"] == "fan":
                has_anomaly = True
                modules[0]["anomaly"] = True
                messages = "팬 밸트가 감속 중 입니다."
                anomalies["fan_belt"] = {
                    "type": "fan_belt",
                    "status": "anomaly",
                    "detail": "slow",
                    "result": "E_SLOW",
                    "message": "팬 벨트가 감속 중입니다.",
                    "percent": {
                        "normal": 10.0,
                        "slow": 80.0,
                        "accel": 0.0,
                        "vibration": 10.0
                    }
                }
                message_str = "팬 벨트가 감속 중 입니다."
                cv_result["has_anomaly"] = True
                cv_result["anomalies"] = anomalies
                cv_result["messages"] = [message_str]
                cv_result["message"] = message_str

            elif device_type == "AHU" and sorted_filtered[0]["label"] == "thermometer":
                has_anomaly = False
                modules[0]["anomaly"] = False
                messages = "온도가 정상입니다."
                anomalies["gauge"] = {
                    "type": "gauge",
                    "status": "normal",
                    "detail": "normal",
                    "result": anomalies["gauge"]["results"],
                    "message": "온도가 정상입니다.",
                }
                message_str = "온도가 정상입니다."
                cv_result["has_anomaly"] = False
                cv_result["anomalies"] = anomalies
                cv_result["messages"] = [message_str]
                cv_result["message"] = message_str
                
            # elif device_type == "AHU" and sorted_filtered[0]["label"] == "thermometer":
            #     has_anomaly = True
            #     modules[0]["anomaly"] = True
            #     messages = "온도계의 온도가 비정상적으로 높습니다."
            #     anomalies["gauge"] = {
            #         "type": "gauge",
            #         "status": "anomaly",
            #         "detail": "thermo_high",
            #         "result": anomalies["gauge"]["results"],
            #         "message": "온도계의 온도가 비정상적으로 높습니다.",
            #     }
            #     message_str = "온도계의 온도가 비정상적으로 높습니다."
            #     cv_result["has_anomaly"] = True
            #     cv_result["anomalies"] = anomalies
            #     cv_result["messages"] = [message_str]
            #     cv_result["message"] = message_str

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
                await broadcast_to(["mobile", "mobile2"], "cv_detection_normal", {
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
            
            # _pending_final_guide = await generate_final_guide(
            #     device_type, modules, anomalies, cv_result, broadcast_to
            # )

            # async with _final_guide_lock:
            #     _pending_final_guide = await generate_final_guide(
            #         device_type, modules, anomalies, cv_result, broadcast_to
            #     )

            _pending_final_guide = {
                    "answer":"fan_belt.slow에 대한 정비 가이드입니다.. 원인은 전원 불균형 또는 전압 강하입니다.. 조치는 인버터 출력 주파수 감소 여부 확인입니다.. 주의사항은 지속적인 감속은 풍량 부족을 야기하여 주의 필요입니다.",
                    "structured_answer":{
                        "error_code":"fan_belt.slow",
                        "markdown_text":"# 🔧 fan_belt.slow\n\n## 🟥 원인\n- 전원 불균형 또는 전압 강하\n\n## 🛠 조치\n1. 인버터 출력 주파수 감소 여부 확인\n\n## ⚠ 주의사항\n- 지속적인 감속은 풍량 부족을 야기하여 주의 필요",
                        "query":"AHU에서 fan_belt.slow에서 이상이 탐지되었습니다",
                        "citations":[
                            {
                                "section":"fan_belt.belt_accelerate",
                                "pages":[-1],
                                "excerpt":"팬/벨트가 비정상적으로 가속될 경우 인버터 출력 주파수를 점검한다. 부하 변화(댐퍼 개도 및 풍량 변화)를 확인한다.\n과속은 모터 과열이나 진동 증가를 초래하므로 즉각 조치가 필요하다."
                            },
                            {
                                "section":"fan_belt.belt_slowdown",
                                "pages":[-1],
                                "excerpt":"팬/벨트가 감속될 경우 인버터 출력 주파수 감소 여부를 확인한다. 전원 불균형 또는 전압 강하를 점검한다. 베어링 마찰 상태를 점검해 윤활 또는 교체한다. 지속적인 감속은 풍량 부족을 야기하므로 주의가 필요하다."
                            },
                            {
                                "section":"fan_belt.belt_vibration",
                                "pages":[-1],
                                "excerpt":"벨트 장력 불균형 여부를 확인해 적정하게 조정한다. 풀리 정렬 상태를 점검하여 편심 여부를 수정한다. 베어링 상태를 점검해 이상 소음 또는 마모가 있는지 확인한다. 과도한 진동은 모터 손상의 주요 원인이므로 즉시 조치해야 한다."
                            }
                        ],
                        "possible_causes_markdown":"#### 🟥 원인\n- 전원 불균형 또는 전압 강하",
                        "recommended_actions_markdown":"#### 🛠 조치\n 인버터 출력 주파수 감소 여부 확인",
                        "safety_warnings_markdown":"#### ⚠ 주의사항\n- 지속적인 감속은 풍량 부족을 야기하여 주의 필요",
                        "possible_causes_audio":"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G1GlcX2M9hixYDuZ//OExNAlucIYAMPYle6g6/vEcoV8Xi43mmPekZhpPB8GJHpGe5jUaxpFWm215rWjNd5lyKkvW06qdH4FclfNo5NAcjvoj2sy5w7dNR9TaOTMzlMkS+Gq0jWVBZR5SWGwjXrNajSV5Vx6aWqu8tZeO2naznd1VWy753lGvuyWi1eTmuHzCSUqJrIL+OFqluW7P41t8yzs01y/ZrbGBMIRlAfZqVuRLNsok3S2KcGlVHoVp74rLuRKpQ2rg9CsvONS//OExOwsnDnsANPM3LyVwitN0rzyWVUezWy2HWiSLhKdlkiJSaJ0JTlFqCgUWpJ5KtEkYkRK2Wo20SRaCU4cyRpSyJ1ovlOokbCVbLbJSyJsLlqLUSOPUk+VczCREq59HWokWgSNKytNKTRJF3np4SNKwkXlPJxdolLROfPJx6CRsU+mlLInWidVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//OExOwtTDmkAPJM3FVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVBnW5/r//////d////X//+7//////+pVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//OExGMFkAlcALgAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVBnW5/r//////d////X//+7//////+pVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//OExGMFkAlcALgAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVBnW5/r//////d////X//+7//////+pVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//OExGMFkAlcALgAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVBnW5/r//////d////X//+7//////+pVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//OExGMFkAlcALgAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVBnW5/r//////d////X//+7//////+pVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//OExGMFkAlcALgAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVBnW5/r//////d////X//+7//////+pVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//OExGMFkAlcALgAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVBnW5/r//////d////X//+7//////+pU8QgEjAOAfMDMAIwSgFjA3A9MAIDwwCAJTAhAEAQJBgLALCEBkHAJAICAAgGioAg0AKGABo8LKXSgPLcBLQugEQFmLkE2DcCrEiGKG//OExGMFkAlcALgAAJgwA+Q9AS4JgZI/hSBJyMEFF+GGLIXEk49BnnUgDrN8/jwJ2Zh0ljL4nUCcZbD3Q48CdmweJJCDnohp5mgd5/GoSwn6eQBpohOrSEH4uWk6EWrkoS0I+NBLHgkkcSCGWheJA9lZAEscB5KIVjgVTYmFcvHpbEsuKSeVEqM8bZVHhXTGpPKh6aE8qJVRYJZeNR0JZeUlskFMyNCYXz4sGaEpVrIFp+YIao8O1yM8O0I9PyQU//OExP9S5DmMAPPY3M2HckIZ8oMy4cm5PKi1WYJ1yJenaUGaRarOGVKs4TrlBmUlJYM0i1WYJzpAJhXXIj9Iy8eHCGjPE65QvgeiXpGUZgnVG5gnaRH5wlQVNeszcAA0MWMSJQoKBxOAiUwEKGQdEcIBQaAJLp8IVIJVsK7UuTlYwycYotxVlgJsQY2TgLESk+ELLyW49kLOEtx8qA4jlPhWI45Uko0acyRUCNQ5cqxVIaulesoaulesocuVYtK1//OExGZA1DnAANvM3ErxaVq6frKuXL9xVza8cla3MbkrW5+6VzaQDhQkgHCRR4YKBjwwUJMDhIowOEij1BQkxQUJMWEgx6BEGPQJETE0SJiaJI9BIiWgkRKTRJFpoki0EiJSaREpNEkWgkSLQSIlJokik0SRcJESoSIlWiSLhEkXCREq1ETrUSNhZE2FkTrUSNtRI2FkTj1kTrUkbC0jYWidakjj1JGmLROVNeBS4MUBhl6Em1WrWcmGYCgmCI/H//OExBUnO2VcAMPGvZ4WfMZKkwD/VjG2LlJHyeqIV7JHpekssCPNur6C1SSyZxBbm1eXTfAvSWE2tTc3wL0zjMkl6b1uts2WVgoYGDBOlgUMDBhHSywGDjked//VgoIFZZWCggQNHllgKof///rLZZxQQMHHlllBxy/+/+1ks+tQUsvZQUiP5VT/8v/401Vcqrp/tNRMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq","possible_causes_audio_encoding":"audio/mpeg","recommended_actions_audio":"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9sGWKbd19EJjJ57HuHdSiMOtayw3fgBn//OExE45xCpgAO4e3Ajw1Kdt245DKQ6db377+efalWRb5lXi7cFiPy58Jl+4IbRga640oXDFKscd++TucqdCy+FwaLGTVnNwki+hbAfqivSV/e/zrWb//5ri//v6//+mt6///zitcZze+Nf0vDh7eNdLQ4lPjO/mPSI8q5zPpIkePvHxj/0+/i2s0+9/Gb+mKZu/Z7wGfdKZgKyJl5r/UN+/3e94d6tB//WpAuVnexg8GsMf25VpnYGB4FAL/VqC//OExBote/aEANva3b3UgrgOlzzr+HYc8K/g08NTqL2/x/A//zt5FWmXfhq9qQwJOdiqftyjkQxxjWxfCfQ800Q5QO7bCdlzGgSlwZFyQ2MBLB6lIwH8S8T8RsFcEBDnG5fJc3J4w44QuQlo9TUlR7kuWl81dV0EFou9SCFX/////1brVs1f/Zbs6fuzrdneg6L66FBdraCCJyfc3c4iZIueMzwcGAl+5OTveW7BfcxeLEAKqeGa2+wGrot7ILku//OExBcsxAKMANvU3cfRYwicxN+2HiyaSFXtPAVkGlnkSGySu61zDfti26fPpG80yYElHCYRcjmaYZfDdL8kC5IczQnB+4KLEbLxjVyGopVQVKnUunFGmhWFoeiBHQbAVgMkgrCKHotDwQwiRqRExpymFx6LJKPSFzTtl+d//////////+iNWysjnEM2bJlK1RiE4qZPIjiMo5Y12Ih1DmY1UGydMcdrXIInJ+HHHLKGN1pltkBjcZAysIEgBuQA//OExBcnQ+Z0AN4K3QQwoALmvZlVmG5t8DEg5sHd5hTy69Wr2vWgshf2OOo1D7AUHXel3MMJTEUvVNaOZleceo2AsFdKkl12tfhmkh7LO9a3S67/75qVX6XW61iJRaZsdxRwGFgFEBdjKHTlR/Se70Fiq3///////////////R1ZSsuVnlKR9D0RRVhRRKKNdb/lWg0RW0RgEYBBKY7hyZA/SaHCyChICgEFtwED5hEHBimJIKFF6qemUDMAQLLn//OExC0m8+JcAOvK3TNnOMnFksZcmZvYyfjjC8EaObeW8800xaXd29q3NJCrDZFa2PFS3q5Oty0lG1zeOcFtgxMQcT41nf+NZ37eDbds/+/9vSjHFhYKYZcWKL2uy//////////+7TJuv60/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","recommended_actions_audio_encoding":"audio/mpeg","safety_warnings_audio":"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//OExFwl/AaMANYK3fned7lve/5vDQ9zlgYew9WN63OYeri5RVCqUpLTf/////////upzqZZzSf+3///9XmVj1IwmgdBNMOYRcKO9A5nKK+5A/5hRp8r4sZeeUlVAHDnWpaibhfq/dDZwRIhhDB8gBgBrDlFshoWGi5RcJgcIqRUnVGJNE88xU9Zw2SpmBFjZZgZl1MolIckc0upoJI3b6/6uyklTCQsZjgo4cJnUgACjIIKNU4kUylHJ/////////OExHcl3A6IANRK3f//+rXQeqKhilYvRu3///5ESrGdxjlY4koi6B3MPVDiqo6lFeCpSdq4Bh1RDgKacNmIjQ8NOSFg5MVaUjjzU4Kh6AlZxDSNF0FoQGfgIijuKpeIcM0fUkipNkkl6T9aPW1FFGtzE1SWal1lpJf///6scdnHhciJLCyFGARPFUgMc1jTTTUR//////////+hzmmodzjlZDlac5pqHG/bVurUNNzrUHo9a5CPWMFUanGkIiSx//OExJImrDJsANzU3Qj1zTSImISUVTAUQzEkCjB8EDGJ7zygWDIIGRIAgQJBkKLAVBQcABGQw3DQHBcutQiAAMAzPkbVFi7WUPPGgBWawqhciqPCYhLDw5BoSHNPVqr2e7NOrusemC1o2mjb+unb9TUeVBuEWJoNwjgVQXQLTTChZiJzYTWE3OfZsGLSCBiJwcDBfc5hmqyMGMAA0ngQHz9SqGigu/HrJvcbKAg4HGC59DSEuiIMmmUyCgSb0Wxi//OExKonqe40AV1QAJDBsOvEwaUmAAcFQKcuUB0xQQRWLVsHM0EhLmdWwJCg0JmWJhjauKBJlKUaWCBBA/buWzkIc7M1MiEDEgAUXjGxM1ZEApZLOW9cL1goAedy5eiEg2XYWKsj9/3XtpT0l+3YkLW4aQwfJz/////iluxnMXrD8Sydme3////85uRyPfb9jsYVXghSeG7PKaXVUPTAQex9v/////9a67H2pcsrHeZ/pk75v2/fbeWeGt1f///v//OExL5I5DpQAZzYAP/zX9/nzdvt3tPT9vXMYnMTblzdSjpojOynfa9WZuSqkhLZd8///v5/r8McsMO4c5g48bib94w3F5Df3DdHNvY0huazX7jb/ug2i2FWRR98srNLInqlLyJdlAPDEgc1X68oSmQ3erveYX0dzfEluU8NIIjNpCcw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2LqCjMYUzKKX///o+kYniSNicPUwHsO0TEcI5VOk6KJqipaKv//////////Ssk6klOv/1Prf///+itHpLR6LLRZIxfwWFUvDNt2MCCE0+9xGKTWTtO0Cww4NzmwjMMD422nzPgQGh+FggLEuFGTDYAAWHrjLnw9oRgGqAMkTAaLg1AjkFwuFcNsHGVBigVOgoyA2hwDJJn846bwK//OExFY6rDpcAZygABUApuFxgtMDFe6kkDRI8VCnHLDAAbOFhoOBg3Z/T/EYDRLZJk4Rcv/W5onZlMyZcKxME2RpPEPGVFWGrADAG//QTf+zB4DIPuUSuVi6RMlxzCBkf///9b/dikZkyTREC6OMoGyciAs8yIsj/6v//XdqSLrTnk3Y3UXCseciBfJgmiNIwZogpbIMNkNVjsGyJ3H8UgR63llqvCDKtA5BD996lFg4kch0BmEZtv7Pvk1+tZlN//OExB4ug+qcAdpoAROUywzJ5dNBLhJQTsS8iksVjoMGJYNiJSOnRiAtALQJgYoDjKRLkQZBqXyQHIOAuHDMdg9QvYVcYQ0NR6Go9zdJFzRZcQW6Caa00FugggggZnjMc44y8WDnKgugjYmZ8voDsPUxxjiHIO0cY9y0lEygPclzdN0EOv/////////XRTPPdBZmnq////WzrdVAuTY0RMC4aGE+hbN0+v//1daSEgUWohblANGBTMbH8InwKtH4//OExBckggqsAMvemP245UQyVxttVKiZ/6wWFkv89iQ4mM+b5hEqFnB8BBIsZmb1o6MQoR/EKFlJ0BjJPCw+gyPIl61tV+/vqtdvHlLywGyrPGU0dKs6cV79TO1Crmx25VYm9sjrbtya2eJDuEA8ed////9W5zZX/8WdAYRAzwG0DFQIGiLUl98/eqFR44dh7jzyeqto2wdTf8/3RRL///fvTb//zqwFv//7kNO/e/9V2kr9bf7NeZdkCTR4fKm1//OExDgmlCKkAMYO3ITTAlb4H3jNsNlYjM7NHMyuWR6RPfzX/Q0r7OpnvtSahm0ROQeCIAoFolmqQCEMgOAMRTh4BQShs1EFIPRoE4L3qNRqYe/O////////////////6OeUqjuhV12NSct2InKmKsZBv86R9ztxKeu5GNJHUXSIrTY5auNFLgWdd/mUw+fP/uUSanlr+/2MQdl3ePH+DjsLG70SWBAn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",
                        "safety_warnings_audio_encoding":"audio/mpeg",
                        "tts_text":"fan_belt.slow에 대한 정비 가이드입니다.. 원인은 전원 불균형 또는 전압 강하입니다.. 조치는 인버터 출력 주파수 감소 여부 확인입니다.. 주의사항은 지속적인 감속은 풍량 부족을 야기하여 주의 필요입니다.",
                        "possible_causes":[],
                        "recommended_actions":[],
                        "safety_warnings":[]},
                        "audio_content":None,
                        "audio_encoding":None,
                        "citations":
                            [
                                {
                                    "section":"fan_belt.belt_accelerate",
                                    "pages":[-1],
                                    "excerpt":"팬/벨트가 비정상적으로 가속될 경우 인버터 출력 주파수를 점검한다. 부하 변화(댐퍼 개도 및 풍량 변화)를 확인한다.\n과속은 모터 과열이나 진동 증가를 초래하므로 즉각 조치가 필요하다."
                                },
                                {
                                    "section":"fan_belt.belt_slowdown",
                                    "pages":[-1],
                                    "excerpt":"팬/벨트가 감속될 경우 인버터 출력 주파수 감소 여부를 확인한다. 전원 불균형 또는 전압 강하를 점검한다. 베어링 마찰 상태를 점검해 윤활 또는 교체한다. 지속적인 감속은 풍량 부족을 야기하므로 주의가 필요하다."
                                },
                                {
                                    "section":"fan_belt.belt_vibration",
                                    "pages":[-1],
                                    "excerpt":"벨트 장력 불균형 여부를 확인해 적정하게 조정한다. 풀리 정렬 상태를 점검하여 편심 여부를 수정한다. 베어링 상태를 점검해 이상 소음 또는 마모가 있는지 확인한다. 과도한 진동은 모터 손상의 주요 원인이므로 즉시 조치해야 한다."
                                }
                            ],
                            "cv_detection_result":{
                                "device_type":"AHU",
                                "modules":[
                                    {
                                        "label":"fan",
                                        "confidence":0.908571183681488,
                                        "x1":265,
                                        "y1":0,
                                        "x2":476,
                                        "y2":242,
                                        "anomaly":True,
                                        "value":None
                                    }
                                ],
                                "anomalies":{
                                    "fan_belt":{
                                        "type":"fan_belt",
                                        "status":"anomaly",
                                        "detail":"slow",
                                        "result":"E_SLOW",
                                        "message":"팬 벨트가 감속 중입니다.",
                                        "percent":{
                                            "normal":10,
                                            "slow":80,
                                            "accel":0,
                                            "vibration":10
                                        }
                                    }
                                },
                        "message":"팬 벨트가 감속 중 입니다."
                        }
                    }

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
            await broadcast_to(["mobile", "mobile2"], "cv_detection_anomaly", payload)
            # await broadcast_to(["mobile", "pc"], "cv_detection_anomaly", payload)

            # ⚠️ 주의: cv_detection_success는 generate_final_guide에서 전송됨 (중복 방지)

        except Exception as e:
            print(f"❌ CV 모델 실행 오류: {e}")
            import traceback
            traceback.print_exc()

            await broadcast_to(["mobile", "mobile2"], "cv_detection_failed", {
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
    global _pending_final_guide
    
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
            
            # if _final_guide_lock.locked():
            #     print("⏳ Final Guide 생성 중... audio_playback_completed 대기 중")
            #     async with _final_guide_lock:
            #         pass
            #     print("✅ Final Guide 생성 완료됨 → 응답 전송 진행")

            if _pending_final_guide:
                await broadcast_to(["mobile", "mobile2"], "final_answer", _pending_final_guide)
                _pending_final_guide = None
            else:
                await broadcast_to(["mobile", "mobile2"], "final_answer", {"answer": "내용 없음"})


            # # 전체 정비 가이드 생성 및 전송 (서비스 사용)
            # await generate_final_guide(device_type, modules, anomalies, cv_result, broadcast_to)
            _pending_cv_detection = None
    
    elif audio_type == "sections_completed":
        # AI_Supporter 섹션별 TTS 재생 완료 → 서비스 종료 버튼 활성화 요청
        print("=" * 80)
        print("✅ [섹션별 TTS 재생 완료] 서비스 종료 버튼 활성화 요청")
        print("=" * 80)
        
        await broadcast_to(["mobile", "mobile2"], "enable_service_end_button", {
            "button_rect": {
                "left": SERVICE_END_BUTTON_RECT[0],
                "top": SERVICE_END_BUTTON_RECT[1],
                "right": SERVICE_END_BUTTON_RECT[2],
                "bottom": SERVICE_END_BUTTON_RECT[3]
            },
            "center": {
                "x": (SERVICE_END_BUTTON_RECT[0] + SERVICE_END_BUTTON_RECT[2]) // 2,
                "y": (SERVICE_END_BUTTON_RECT[1] + SERVICE_END_BUTTON_RECT[3]) // 2
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
        # 이거 이제 안씀
        # try:
        #     await broadcast_to("mobile", "start_sse_connection", {
        #         "text": stt_text,
        #         "timestamp": None
        #     })
        #     await wait_for_next_step("SSE 연결 시작 요청 전송 완료", "6-1")
        # except Exception as e:
        #     print(f"⚠️ SSE 연결 시작 요청 전송 실패: {e}")
        
        # 2. Gemini-Flash로 Intent 분류 및 모바일로 전송
        try:
            intent_result = classify_intent(stt_text)
            intent = intent_result.get("intent", "AI_SUPPORTER")
            
            await wait_for_next_step("Intent 분류 완료", "7")
            
            # 모바일로 Intent 결과 전송
            await broadcast_to(["mobile", "mobile2"], "intent_result", {
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
            await broadcast_to(["mobile", "mobile2"], "intent_result", {
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
        # 프레임이 문자열인 경우 (base64 또는 다른 인코딩) 처리
        if isinstance(frame_bytes, str):
            import base64
            try:
                frame_bytes = base64.b64decode(frame_bytes)
            except Exception:
                frame_bytes = frame_bytes.encode('latin-1')  # fallback
        
        # 바이너리가 아닌 경우 에러
        if not isinstance(frame_bytes, bytes):
            return
        
        np_data = np.frombuffer(frame_bytes, np.uint8)
        frame_original = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        if frame_original is None:
            return
        
        # 원본 프레임 저장 (제스처 인식용 - 좌표계 일치를 위해 반전하지 않음)
        # frame_for_gesture = frame_original.copy()
        
        # 반전된 프레임 생성 (AR 마커/모션 추정용)
        try:
            # frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            frame_flipped = cv2.flip(frame_original, -1)
        except Exception as e:
            print(f"⚠️ Frame rotation error: {e}")
            frame_flipped = frame_original
    except Exception as e:
        print(f"⚠️ Frame decode error: {e}")
        return

    # 프레임 스트림에 추가 (최근 N개만 유지) - 반전된 프레임 사용
    try:
        from app.services.frame_collector import add_frame
        await add_frame(frame_flipped, timestamp)
    except Exception as e:
        print(f"⚠️ 프레임 스트림 추가 오류: {e}")

    # 모션 추정 (Optical Flow + RANSAC + Essential) - 반전된 프레임 사용
    result = motion_core.process_frame(frame_flipped)
    if result["status"] not in ("ok", "init"):
        _, jpeg_bytes = cv2.imencode(".jpg", frame_flipped)
        await broadcast_to('pc', "video_frame", {
            "timestamp": timestamp,
            "frame": jpeg_bytes.tobytes()
        })
        await broadcast_to(['mobile', "mobile2"], "video_frame", jpeg_bytes.tobytes())
        return

    # AR 마커 업데이트 및 브로드캐스트 - 반전된 프레임 사용
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
        await broadcast_to(['pc', 'mobile', "mobile2"], "ar-info", {"markers": ar_markers})

    # ================================
    # 제스처로 서비스 종료 버튼 클릭 감지
    # 원본 프레임 사용 (반전되지 않은 프레임) - 모바일 화면 좌표계와 일치
    # ================================
    # if gesture_manager.enabled:
    #     await gesture_manager.handle_frame(
    #         frame_for_gesture,
    #         on_gesture_service_start,
    #         on_gesture_service_end
    #     )

    # ================================
    # 이후 PC/모바일로 프레임 전송
    # ================================
    # PC로 프레임 전송 (timestamp 포함) - 반전된 프레임 사용
    _, jpeg_bytes = cv2.imencode(".jpg", frame_flipped)
    await broadcast_to('pc', "video_frame", {
        "timestamp": timestamp,
        "frame": jpeg_bytes.tobytes()
    })
    await broadcast_to(['mobile', "mobile2"], "video_frame", jpeg_bytes.tobytes())
    
    try:
        yolo_res = await get_latest_yolo_result()
        if yolo_res:
            frame_ts = yolo_res.get("frame_ts")
            if frame_ts and abs(frame_ts - timestamp) <= 200:
                payload = {
                    "timestamp": frame_ts,
                    "boxes": yolo_res.get("boxes", []),
                }
                await broadcast_to(['pc', 'mobile', "mobile2"], "video_overlay", payload)
    except Exception as e:
        print(f"⚠️ YOLO overlay 전송 오류: {e}")


# # ========================================
# # mobile로부터 mediapipe on 이벤트 받으면 켜기
# # ========================================
# async def handle_active_mediapipe(sid, data):
#     """
#     모바일로부터 active_mediapipe 이벤트 수신
#     - data는 None일 수 있음 (모바일에서 null을 보낼 수 있음)
#     - rect 정보가 없으면 하드코딩된 좌표 사용
#     """
#     try:
#         sender_device = device_map.get(sid, "unknown")
        
#         if sender_device != "mobile":
#             return

#         # 모바일에서 rect 정보가 있으면 사용, 없으면 하드코딩된 좌표 사용
#         rect = None
        
#         if data is None:
#             rect = None
#         elif isinstance(data, (list, tuple)) and len(data) > 0:
#             first_item = data[0]
#             if isinstance(first_item, dict):
#                 rect = first_item.get("rect") if first_item else None
#         elif isinstance(data, dict):
#             rect = data.get("rect")
#         elif hasattr(data, 'get') and callable(getattr(data, 'get', None)):
#             try:
#                 if data is not None:
#                     rect = data.get("rect")
#             except (AttributeError, TypeError):
#                 rect = None
        
#         if rect and isinstance(rect, dict):
#             button_rect = (
#                 rect.get('left'),
#                 rect.get('top'),
#                 rect.get('right'),
#                 rect.get('bottom')
#             )
#             if not all(v is not None for v in button_rect):
#                 button_rect = SERVICE_END_BUTTON_RECT
#         else:
#             button_rect = SERVICE_END_BUTTON_RECT
        
#         gesture_manager.enabled = True
#         gesture_manager.button_rect = button_rect

#         # START 모드 요청 (첫 번째 active_mediapipe 호출)
#         if not gesture_manager.waiting_for_start and not gesture_manager.waiting_for_end:
#             gesture_manager.waiting_for_start = True
#             print("✅ [Gesture] 서비스 시작 버튼 클릭 대기 모드", flush=True)
#             return

#         # END 모드 요청 (두 번째 active_mediapipe 호출)
#         if gesture_manager.waiting_for_start and not gesture_manager.waiting_for_end:
#             gesture_manager.waiting_for_start = False
#             gesture_manager.waiting_for_end = True
#             print("✅ [Gesture] 서비스 종료 버튼 클릭 대기 모드", flush=True)
#             return

#         # 그 외: 다시 초기화
#         gesture_manager.waiting_for_start = True
#         gesture_manager.waiting_for_end = False
#     except Exception as e:
#         print(f"❌ [Gesture] active_mediapipe 처리 오류: {e}", flush=True)
#         # 에러가 발생해도 기본 좌표로 설정하여 서비스가 계속 작동하도록 함
#         try:
#             gesture_manager.enabled = True
#             gesture_manager.button_rect = SERVICE_END_BUTTON_RECT
#         except Exception:
#             pass

# # ========================================
# # mediapipe에서 시작 버튼 눌렸을 때 FastAPI 반응(gesture start 콜백)
# # ========================================
# async def on_gesture_service_start():
#     print("✅ [Gesture] 서비스 시작 버튼 클릭", flush=True)
#     await broadcast_to("mobile", "service_start_clicked", {})
#     await trigger_start_pipeline("gesture")

# # ========================================
# # mediapipe에서 종료 버튼 눌렸을 때 FastAPI 반응(gesture end 콜백)
# # ========================================
# async def on_gesture_service_end():
#     print("✅ [Gesture] 서비스 종료 버튼 클릭", flush=True)
#     await broadcast_to("mobile", "service_end_clicked", {})
    
#     global _pending_cv_detection
#     gesture_manager.enabled = False
#     _pending_cv_detection = None
#     await broadcast_to("raspi", "audio_playback_completed", {})

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
    sender_device =device_map.get(sid, "unknown")
    if sender_device == "unknown" or sender_device == "mobile2":
        return

    global ar_markers
    ar_markers.clear()

    await broadcast_to("raspi", "handle_audio_stream", {"start": True})
    await asyncio.sleep(0.3)

    description = {
        "type": "description",
        "idx": -1,
        "info": {
            "x": -100000.0,
            "y": -100000.0,
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
    global ar_markers
    
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown" or sender_device == "mobile2":
        return

    await broadcast_to("raspi", "handle_audio_stream", {"start": False})
    ar_markers.clear()
    await asyncio.sleep(0.3)
    
    await broadcast_to(["mobile", "mobile2"], "communication_close", {})
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
    if sender_device != "mobile" and sender_device != "mobile2":
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
    await broadcast_to(['pc', 'mobile', 'mobile2'], "ar-info", {"markers": ar_markers})

async def delete_marker(sid, data):
    """
    전달받은 idx에 해당하는 AR 마커 삭제
    """
    sender_device = device_map.get(sid, "unknown")
    if sender_device == "unknown" or sender_device == "mobile2":
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
    
    await broadcast_to(['pc', 'mobile', "mobile2"], "ar-info", {"markers": ar_markers})

async def handle_wakeword_force(sid, data):
    print(f"wakeword 강제화 전송 받음")
    sender_device = device_map.get(sid, "unknown")
    if sender_device != "mobile" and sender_device != "unknown":     # 모바일 또는 서버에서 요청 제외하고는 무시
        return
    await broadcast_to("raspi", "wakeword_force", {})
    print("라즈베리파이로 전송완료")

    