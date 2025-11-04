import threading
import asyncio
import uvicorn
from stt.mic_stream import MicStream
from stt.gcp_stt_buffered import GcpBufferedStt
from stt.wakeword_hook import wait_for_wakeword, init_wakeword_detector, stop_wakeword_detector
from stt.webhook_client import send_stt_start_webhook
from server.app import app, manager

def run_stt_loop():
    """
    메인 STT 루프
    설계에 따른 동작 흐름:
    ① 대기 (마이크 OFF)
    ② Wakeword 감지
    ③ Webhook 알림 전송 (HTTP POST)
    ④ 마이크 활성화 (ON)
    ⑤ 음성 수집 (3~5초)
    ⑥ STT 요청 (GCP)
    ⑦ STT 결과 수신
    ⑧ 결과 전송 (WebSocket)
    ⑨ 마이크 종료 / 세션 종료 (OFF)
    """
    # 마이크 초기화 (아직 시작하지 않음)
    mic = MicStream()
    mic.start()  # 스트림 생성 후
    mic.pause()  # 즉시 일시 정지 (대기 상태, 마이크 OFF)
    
    # STT 인스턴스 생성
    stt = GcpBufferedStt()
    
    # Wakeword 감지기 초기화
    init_wakeword_detector()
    
    # 이벤트 루프 생성
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def broadcast(msg):
        """WebSocket으로 메시지 브로드캐스트"""
        await manager.broadcast(msg)

    async def stt_session():
        """STT 세션 실행"""
        # ④ 마이크 활성화
        mic.resume()
        
        # ⑤⑥⑦ STT 실행 (음성 수집 + 요청 + 결과 수신)
        await stt.run(mic, broadcast)
        
        # ⑨ 마이크 종료
        mic.pause()

    print("🎧 STT 루프 대기 시작 (마이크 OFF)")
    try:
        while True:
            # ① 대기 상태 (마이크 OFF)
            # ② Wakeword 감지 대기
            if wait_for_wakeword():
                print("🚀 Wakeword 감지됨: STT 세션 시작")
                
                # ③ Webhook 알림 전송 (HTTP POST)
                webhook_sent = send_stt_start_webhook()
                if not webhook_sent:
                    print("⚠️ Webhook 전송 실패 (계속 진행)")
                
                # ④~⑨ STT 세션 실행
                loop.run_until_complete(stt_session())
                
                print("🟢 STT 세션 종료, 다시 대기 중... (마이크 OFF)")
    except KeyboardInterrupt:
        print("🛑 종료 중...")
        mic.stop()
        stop_wakeword_detector()
        print("✅ 종료 완료")

if __name__ == "__main__":
    t = threading.Thread(target=run_stt_loop, daemon=True)
    t.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
