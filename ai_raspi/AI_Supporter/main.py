import threading
import asyncio
import logging
import json
from stt.mic_stream import MicStream
from stt.gcp_stt_buffered import GcpBufferedStt
from stt.gcp_stt_stream import GcpStreamingStt
from stt.wakeword_hook import wait_for_wakeword, init_wakeword_detector, stop_wakeword_detector
from stt.socketio_client import SocketIOClient
from server.app import manager  # manager만 사용 (app은 레거시)
from config import settings

# 로깅 설정
logging.basicConfig(level=logging.INFO)

def run_stt_loop():
    """
    메인 STT 루프
    설계에 따른 동작 흐름:
    ① 대기 (마이크 ON, Wakeword 감지 중)
    ② Wakeword 감지
    ③ 버퍼링 방식 STT 실행 (마이크 ON 상태)
    ④ 텍스트 전송 → 마이크 OFF (Intent 분류 중간)
    ⑤ Intent 분류 완료 후 모드 전환
    ⑥ 스트리밍 방식 STT 시작 (마이크 ON)
    ⑦ 서비스 종료 → STT 세션 OFF (마이크는 계속 ON)
    ⑧ 대기 복귀 (마이크 ON, 다음 Wakeword 대기)
    
    참고: 마이크는 항상 켜져있고, 버퍼링 STT 후 Intent 분류 중간에만 OFF됩니다.
    Socket.IO 클라이언트가 자동으로 서버에 연결되어 디바이스 등록을 수행합니다.
    모드 전환은 모바일에서 Socket.IO를 통해 제어 명령을 전송합니다.
    """
    # 마이크 초기화 및 시작 (항상 켜져있음)
    mic = MicStream()
    mic.start()  # 스트림 생성 및 시작 (마이크 ON)
    print("🔊 마이크 ON (항상 활성 상태)")
    
    # 마이크 인스턴스를 manager에 등록 (Socket.IO 제어 명령에서 접근 가능하도록)
    manager.set_mic_stream(mic)
    
    # Socket.IO 클라이언트 초기화 및 연결
    socketio_client = SocketIOClient(manager=manager)  # manager 전달
    manager.set_socketio_client(socketio_client)
    
    # 이벤트 루프 생성
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Socket.IO 연결 (비동기로 실행)
    async def connect_socketio():
        """Socket.IO 서버 연결"""
        try:
            connected = await socketio_client.connect()
            if connected:
                print(f"✅ Socket.IO 서버 연결 성공: {settings.FASTAPI_SERVER_URL} (경로: /ws)")
            else:
                print(f"⚠️ Socket.IO 서버 연결 실패: {settings.FASTAPI_SERVER_URL}")
        except Exception as e:
            print(f"❌ Socket.IO 연결 오류: {e}")
    
    # Socket.IO 연결 실행
    loop.run_until_complete(connect_socketio())
    
    # STT 인스턴스 생성
    buffered_stt = GcpBufferedStt()
    streaming_stt = GcpStreamingStt()
    
    # Streaming STT 인스턴스를 manager에 등록 (종료 신호 처리용)
    manager.set_streaming_stt_instance(streaming_stt)
    
    # Wakeword 감지기 초기화
    init_wakeword_detector()

    async def broadcast(msg):
        """WebSocket으로 메시지 브로드캐스트"""
        await manager.broadcast(msg)

    async def stt_session():
        """STT 세션 실행 (모드에 따라 버퍼링/스트리밍 선택)"""
        try:
            # 모드 확인
            mode = manager.get_stt_mode()
            print(f"📝 STT 모드: {mode}")
            
            if mode == "buffered":
                # 버퍼링 방식: 3~5초 수집 후 일괄 처리 (분기처리 이전)
                # 마이크는 이미 켜져있음
                await buffered_stt.run(mic, broadcast)
                # 버퍼링 STT 후 텍스트 전송 완료 → 마이크는 buffered_stt.run() 내부에서 OFF됨
            else:
                # 스트리밍 방식: 실시간 인식 (분기처리 이후)
                # Intent 분류 완료 후 스트리밍 모드로 전환됨
                print("🎤 스트리밍 모드 시작 (실시간 음성 인식)")
                # 마이크 다시 활성화 (Intent 분류 중간에 OFF되었으므로)
                if not mic.stream.is_active():
                    mic.resume()
                    print("🔊 마이크 ON (스트리밍 모드 시작)")
                
                # Streaming STT 인스턴스에 Socket.IO 클라이언트 설정
                streaming_stt.socketio_client = socketio_client
                
                # 세션 ID 생성 (Clarify 세션용)
                import uuid
                session_id = str(uuid.uuid4())
                
                print(f"📤 Socket.IO를 통해 Streaming STT 전송 시작 (session_id={session_id})")
                await streaming_stt.run(mic, broadcaster=broadcast, session_id=session_id)
                # 스트리밍 종료 후 마이크는 켜둠 (다음 Wakeword 대기)
                print("🟢 스트리밍 모드 종료, 마이크는 계속 ON")
                
        except Exception as e:
            print(f"❌ STT 세션 오류: {e}")
            # 에러 발생 시에도 마이크는 켜둠 (다음 Wakeword 대기를 위해)
            if not mic.stream.is_active():
                mic.resume()

    print("🎧 STT 루프 대기 시작 (마이크 ON, Wakeword 감지 중)")
    print("📌 모드 전환: 모바일에서 Socket.IO를 통해 제어 명령 전송")
    try:
        while True:
            # ① 대기 상태 (마이크 ON, Wakeword 감지 중)
            # ② Wakeword 감지 대기
            if wait_for_wakeword():
                print("🚀 Wakeword 감지됨: STT 세션 시작")
                
                # ③~⑦ STT 세션 실행 (모드에 따라 버퍼링/스트리밍)
                loop.run_until_complete(stt_session())
                
                print("🟢 STT 세션 종료, 다시 대기 중... (마이크 ON, 다음 Wakeword 대기)")
    except KeyboardInterrupt:
        print("🛑 종료 중...")
        streaming_stt.stop()
        # Socket.IO 연결 종료
        loop.run_until_complete(socketio_client.disconnect())
        mic.stop()
        stop_wakeword_detector()
        print("✅ 종료 완료")

if __name__ == "__main__":
    """
    라즈베리파이 메인 프로그램
    - 클라이언트로만 동작 (Socket.IO 클라이언트)
    - 모든 통신은 Socket.IO를 통해 FastAPI 서버로 전송
    - HTTP 서버(uvicorn)는 사용하지 않음
    """
    # STT 루프 실행 (무한 루프이므로 여기서 멈춤)
    run_stt_loop()
