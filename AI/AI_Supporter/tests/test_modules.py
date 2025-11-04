"""
개별 모듈 테스트 스크립트
각 모듈을 독립적으로 테스트할 수 있습니다.
"""
import sys
import os
import time
import asyncio

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stt.mic_stream import MicStream
from stt.wakeword_detector import WakewordDetector
from stt.webhook_client import send_stt_start_webhook
from config import settings

def test_mic_stream():
    """마이크 스트림 테스트"""
    print("=" * 50)
    print("🎤 마이크 스트림 테스트")
    print("=" * 50)
    
    mic = MicStream()
    mic.start()
    print("✅ 마이크 시작")
    
    # pause 테스트
    time.sleep(1)
    print("\n⏸️  마이크 일시 정지 테스트...")
    mic.pause()
    time.sleep(1)
    
    # resume 테스트
    print("▶️  마이크 재개 테스트...")
    mic.resume()
    time.sleep(1)
    
    # 데이터 읽기 테스트
    print("\n📥 데이터 읽기 테스트 (3초)...")
    start = time.time()
    chunk_count = 0
    while time.time() - start < 3:
        chunk = mic.read()
        if chunk:
            chunk_count += 1
            if chunk_count % 10 == 0:
                print(f"   읽은 청크: {chunk_count}개")
    
    print(f"✅ 총 {chunk_count}개 청크 읽음")
    mic.stop()
    print("✅ 마이크 종료")

def test_wakeword_detector():
    """Wakeword 감지기 테스트"""
    print("\n" + "=" * 50)
    print("🎧 Wakeword 감지기 테스트")
    print("=" * 50)
    print("⚠️  'onAir'라고 말해보세요 (신뢰도 > 0.75)")
    print("   10초 후 자동 종료됩니다.\n")
    
    detector = WakewordDetector()
    detector.start()
    
    try:
        detected = detector.wait_for_wakeword(timeout=10)
        if detected:
            print("✅ Wakeword 감지 성공!")
        else:
            print("⏱️  타임아웃 (10초 내 감지 실패)")
    except KeyboardInterrupt:
        print("\n⚠️  사용자 중단")
    finally:
        detector.stop()

def test_webhook():
    """Webhook 전송 테스트"""
    print("\n" + "=" * 50)
    print("🌐 Webhook 전송 테스트")
    print("=" * 50)
    
    print(f"서버 URL: {settings.APP_SERVER_URL}")
    print(f"엔드포인트: {settings.WEBHOOK_ENDPOINT}")
    
    result = send_stt_start_webhook()
    if result:
        print("✅ Webhook 전송 성공")
    else:
        print("❌ Webhook 전송 실패")
        print("   테스트 서버를 실행하려면:")
        print("   python tests/test_webhook_server.py")

def test_stt_buffered():
    """STT 버퍼링 테스트 (실제 GCP 호출)"""
    print("\n" + "=" * 50)
    print("🗣️  STT 버퍼링 테스트")
    print("=" * 50)
    print("⚠️  실제 GCP API를 호출합니다.")
    print("   3~5초 동안 말해보세요.\n")
    
    from stt.gcp_stt_buffered import GcpBufferedStt
    
    mic = MicStream()
    mic.start()
    mic.resume()
    
    stt = GcpBufferedStt()
    
    async def test():
        async def broadcaster(msg):
            print(f"📨 브로드캐스트: {msg}")
        
        await stt.run(mic, broadcaster)
        mic.stop()
    
    try:
        asyncio.run(test())
        print("✅ STT 테스트 완료")
    except KeyboardInterrupt:
        print("\n⚠️  사용자 중단")
        mic.stop()

def main():
    """메인 테스트 메뉴"""
    print("\n" + "=" * 50)
    print("🧪 모듈 테스트 스크립트")
    print("=" * 50)
    print("\n테스트할 모듈을 선택하세요:")
    print("1. 마이크 스트림 테스트")
    print("2. Wakeword 감지기 테스트")
    print("3. Webhook 전송 테스트")
    print("4. STT 버퍼링 테스트 (GCP 호출)")
    print("5. 전체 테스트")
    print("0. 종료")
    
    choice = input("\n선택: ").strip()
    
    if choice == "1":
        test_mic_stream()
    elif choice == "2":
        test_wakeword_detector()
    elif choice == "3":
        test_webhook()
    elif choice == "4":
        test_stt_buffered()
    elif choice == "5":
        test_mic_stream()
        test_webhook()
        test_wakeword_detector()
        print("\n✅ 전체 테스트 완료")
    elif choice == "0":
        print("👋 종료")
        sys.exit(0)
    else:
        print("❌ 잘못된 선택")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 종료")

