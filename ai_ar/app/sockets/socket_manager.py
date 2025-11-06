# 📄 app/sockets/socket_manager.py
import socketio
import os
import cv2
import numpy as np
from datetime import datetime

print(f"🔔 [DEBUG] socket_manager.py 모듈 로드 시작")

# 비동기 Socket.IO 서버 생성
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*'
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


# === 타입별 브로드캐스트 ===
async def broadcast_to(device_types, event: str, payload: dict):
    """
    특정 디바이스 타입(하나 또는 여러 개)에 이벤트 전송
    - device_types: 문자열('raspi') 또는 리스트(['raspi', 'mobile'])
    """
    if isinstance(device_types, str):
        device_types = [device_types]

    sent_count = 0
    for sid, dev in device_map.items():
        if dev in device_types:
            await sio.emit(event, payload, to=sid)
            sent_count += 1

    print(f"📡 Broadcasted '{event}' to {sent_count} clients ({device_types})")


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


# === video-frame (라즈베리 → 서버 프레임 전송) ===
@sio.on("video_frame")
async def handle_video_frame(sid, data):
    print("프레임 들어옴")
    # from app.ar import motion_core
    """
    라즈베리파이에서 binary 형태로 전송된 JPEG 프레임 처리
    """
    sender_device = device_map.get(sid, "unknown")

    if not data:
        return

    # data는 bytes (JPEG 이미지)
    np_data = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
    print("프레임")
    print(frame)
    if frame is None:
        print("⚠️ Failed to decode frame")
        return

    print(f"🎞️ Received frame from {sender_device}")

    # ✅ 모션 계산 수행 (카메라 위치 추정)
    # result = await motion_core.process_frame(frame, sid=sid)

    # ✅ 계산 결과 확인 로그
    # if result["status"] == "ok":
    #     x, y, z = result["x"], result["y"], result["z"]
    #     print(f"📍 Camera position: x={x:.3f}, y={y:.3f}, z={z:.3f}")
    # else:
    #     print(f"⚠️ Motion estimation status: {result['status']}")

    # 동시에 PC 클라이언트에게 원본 프레임 브로드캐스트
    _, jpeg_bytes = cv2.imencode('.jpg', frame)
    await broadcast_to("pc", "video_frame", jpeg_bytes.tobytes())
    

# === STT 결과 수신 및 FastAPI 서버로 전달 ===
print(f"🔔 [DEBUG] stt_result 이벤트 핸들러 등록 시작")

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
                "session_id": "uuid" (optional)  # Streaming STT용
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
            fastapi_url = os.getenv("FASTAPI_SERVER_URL", "http://localhost:8000")
            endpoint = f"{fastapi_url}/api/stt/buffered"
            
            # session_id 포함 (Streaming STT용)
            stt_data = {
                **data,  # type, text, confidence
                "session_id": data.get("session_id")  # Clarify 세션 ID (있는 경우)
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

# === Clarify 입력 수신 및 FastAPI 서버로 전달 ===
@sio.on("clarify_input")
async def handle_clarify_input(sid, data):
    """
    모바일에서 전송된 Clarify 입력을 수신하여 FastAPI 서버로 전달
    
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
    sender_device = device_map.get(sid, "unknown")
    
    # 모바일에서만 받음
    if sender_device != "mobile":
        print(f"⚠️ Clarify 입력은 모바일에서만 받을 수 있습니다. 수신자: {sender_device}")
        return
    
    text = data.get("text", "")
    session_id = data.get("session_id", "")
    
    print(f"💬 Clarify 입력 수신 [mobile]: text={text[:50]}..., session_id={session_id}")
    
    # FastAPI 서버로 전달
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            fastapi_url = os.getenv("FASTAPI_SERVER_URL", "http://localhost:8000")
            endpoint = f"{fastapi_url}/api/clarify/response"
            
            response = await client.post(
                endpoint,
                json={
                    "session_id": session_id,
                    "turn_id": data.get("turn_id", 1),
                    "response": text,
                    "action": data.get("action", "continue")
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                # FastAPI에서 이미 socket_manager로 브로드캐스트하므로
                # 여기서는 별도 브로드캐스트 불필요
                print(f"✅ Clarify 응답 처리 완료")
            else:
                print(f"⚠️ FastAPI 서버 응답 오류: {response.status_code}")
    except Exception as e:
        print(f"❌ FastAPI 서버 전달 오류: {e}")

