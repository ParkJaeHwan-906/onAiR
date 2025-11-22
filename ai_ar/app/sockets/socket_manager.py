# 📄 app/sockets/socket_manager.py
import socketio
import os
import cv2
import numpy as np
from datetime import datetime
from app.ar import motion_core


# 서버 측 socket_manager.py
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    ping_timeout=20,    # 기본값 5초 → 늘려서 여유 줌
    ping_interval=10    # 기본값 25초 → 조금 짧게 하여 안정적 유지
)

print(f"🔔 [DEBUG] Socket.IO 서버 인스턴스 생성 완료")

# 클라이언트별 디바이스 타입 저장용
device_map = {}   # { sid: "raspi" / "mobile" / "pc" }

# === 이벤트 정의 ===
@sio.event
async def connect(sid, environ):
    print(f"✅ Client connected: {sid}")
    await sio.emit("server_message", {"msg": "Connected"}, to=sid)


@sio.event
async def disconnect(sid):
    print(f"❌ Disconnected: {sid}")
    # 연결 종료 시 기록 삭제
    if sid in device_map:
        print(f"🧹 Removing device: {device_map[sid]}")
        disconnected_device = device_map.get(sid, "unknown")
        await broadcast_to("raspi", "video_stream", {"state": "off"})
        del device_map[sid]



@sio.on("register_device")
async def register_device(sid, data):
    """
    클라이언트에서 {'device': 'raspi'} 형태로 등록 요청
    """
    device = data.get("device", "unknown")
    device_map[sid] = device
    await sio.save_session(sid, {"device": device})

    print(f"🔗 Registered device: {device} ({sid})")
    await sio.emit("server_message", {"msg": f"Device '{device}' registered"}, to=sid)


@sio.on("ping")
async def handle_ping(sid, data):
    session = await sio.get_session(sid)
    device = session.get("device", "unknown")
    print(f"📡 Received ping from [{device}] {sid}: {data}")
    await sio.emit("pong", {"msg": f"Pong from server to {device}!"}, to=sid)


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

    # 디버깅용 로그 (필요 시 활성화)
    # print(f"📡 Broadcasted '{event}' to {sent_count} clients ({device_types})")



# === video_stream ===
@sio.on("video_stream")
async def handle_video_stream(sid, data):
    """
    PC/Mobile → Raspi로 영상 스트리밍 제어 신호 전달
    """
    sender_device = device_map.get(sid, "unknown")
    state = data.get("state", "off")

    print(f"📡 Received 'video_stream:{state}' from {sender_device}")
    await broadcast_to("raspi", "video_stream", {"state": state})

# @sio.on("video_frame")
# async def handle_video_frame(sid, data):
#     """라즈베리파이 → JPEG binary 수신 후 모션 추정"""
#     sender_device = device_map.get(sid, "unknown")
#     if not data:
#         return

#     np_data = np.frombuffer(data, np.uint8)
#     frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
#     if frame is None:
#         print("⚠️ Failed to decode frame")
#         return

#     # === 모션 계산 ===
#     result = await motion_core.process_frame(frame, sid=sid)

#     # === 결과 전송 ===
#     if result["status"] == "ok":
#         x, y, z = result["x"], result["y"], result["z"]
#         print(f"📍 Camera position: x={x:.3f}, y={y:.3f}, z={z:.3f}")
#         await broadcast_to("pc", "ar_marker", {"x": x, "y": y, "z": z})
#     else:
#         print(f"⚠️ Motion estimation status: {result['status']}")

#     # === 프레임 브로드캐스트 (PC 디스플레이용) ===
#     _, jpeg_bytes = cv2.imencode(".jpg", frame)
#     await broadcast_to("pc", "video_frame", jpeg_bytes.tobytes())
    

# # === STT 결과 수신 및 FastAPI 서버로 전달 ===
# print(f"🔔 [DEBUG] stt_result 이벤트 핸들러 등록 시작")

@sio.on("stt_result")
async def handle_stt_result(sid, data):
    print(f"🔔 [DEBUG] ⭐⭐⭐ handle_stt_result 함수가 호출되었습니다! ⭐⭐⭐")
    """
    라즈베리파이에서 전송된 버퍼링 STT 결과를 수신하여:
    1. 모바일로 브로드캐스트 (Intent 분류용)
    2. FastAPI 서버로 전달 (임베딩/처리용)
    
    Args:
        sid: 클라이언트 세션 ID
        data: STT 결과 딕셔너리
            {
                "type": "final" | "interim" | "error" | "info",
                "text": "인식된 텍스트",
                "confidence": 0.95 (optional),
            }
    """
    print(f"🔔 [DEBUG] handle_stt_result 호출됨! sid={sid}, data={data}")
    print(f"🔔 [DEBUG] device_map={device_map}")
    
    sender_device = device_map.get(sid, "unknown")
    print(f"🔔 [DEBUG] sender_device={sender_device}")
    
    # 라즈베리파이에서만 받음
    if sender_device != "raspi":
        print(f"⚠️ STT 결과는 라즈베리파이에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    stt_type = data.get("type", "unknown")
    stt_text = data.get("text", "")
    confidence = data.get("confidence")
    
    print(f"📝 STT 결과 수신 [raspi]: type={stt_type}, text={stt_text[:50]}...")
    
    # 1. 모바일로 브로드캐스트 (Intent 분류용)
    await broadcast_to("mobile", "stt_result", data)
    print(f"📤 STT 결과를 모바일로 전달 완료")
    
    # 2. FastAPI 서버로 전달 (임베딩/처리용)
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            fastapi_url = os.getenv("FASTAPI_SERVER_URL", "http://k13a407.p.ssafy.io/ai")
            endpoint = f"{fastapi_url}/api/stt/buffered"
            
            stt_data = {
                **data  # type, text, confidence
            }
            
            print(f"📡 FastAPI 서버로 STT 결과 전달 시도: {endpoint}")
            print(f"   데이터: {stt_data}")
            
            response = await client.post(
                endpoint,
                json=stt_data,
                timeout=30.0  # 타임아웃 증가 (임베딩 추출 시간 고려)
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ FastAPI 서버로 STT 결과 전달 성공")
                print(f"   응답: {result.get('message', 'N/A')}")
            else:
                print(f"⚠️ FastAPI 서버 응답 오류: {response.status_code}")
                print(f"   응답 내용: {response.text[:200]}")
    except httpx.ConnectError as e:
        print(f"❌ FastAPI 서버 연결 실패: {e}")
        print(f"   FastAPI 서버가 실행 중인지 확인하세요: {fastapi_url}")
    except httpx.TimeoutException as e:
        print(f"❌ FastAPI 서버 요청 타임아웃: {e}")
        print(f"   임베딩 추출에 시간이 오래 걸리고 있습니다.")
    except Exception as e:
        print(f"❌ FastAPI 서버 전달 오류: {e}")
        import traceback
        traceback.print_exc()


# === 라즈베리파이 제어 이벤트 (모바일 → 라즈베리파이) ===
@sio.on("control_raspi")
async def handle_control_raspi(sid, data):
    """
    모바일에서 전송된 라즈베리파이 제어 명령을 수신하여 라즈베리파이로 전달
    
    Args:
        sid: 클라이언트 세션 ID
        data: 제어 명령 딕셔너리
            {
                "command": "start_streaming_stt" | "set_stt_mode",
                "mode": "buffered" | "streaming" (set_stt_mode일 때),
                "branch": "AI_SUPPORTER" | "OPERATOR" (notifyIntentDone일 때)
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

