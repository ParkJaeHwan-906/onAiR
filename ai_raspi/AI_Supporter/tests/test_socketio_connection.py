"""
Socket.IO 연결 테스트 스크립트

Socket.IO 서버 연결 및 이벤트 수신을 테스트합니다.
이 스크립트로 라즈베리파이에서 STT 결과가 Socket.IO로 잘 전송되는지 확인할 수 있습니다.

사용 방법:
    python tests/test_socketio_connection.py --socketio-url http://localhost:5000
"""
import asyncio
import socketio
import sys
import argparse
from datetime import datetime


class SocketIOTestClient:
    """Socket.IO 테스트 클라이언트"""
    
    def __init__(self, url: str):
        self.url = url
        self.sio = socketio.AsyncClient()
        self.setup_handlers()
    
    def setup_handlers(self):
        """이벤트 핸들러 설정"""
        
        @self.sio.on('connect')
        async def on_connect():
            print(f"\n✅ Socket.IO 서버 연결 성공!")
            print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 디바이스 등록 (mobile 타입으로 등록)
            await self.sio.emit('register_device', {'device_type': 'mobile'})
            print("   📱 디바이스 등록 완료 (타입: mobile)")
        
        @self.sio.on('disconnect')
        async def on_disconnect():
            print(f"\n🔌 Socket.IO 서버 연결 종료")
            print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        @self.sio.on('server_message')
        async def on_server_message(data):
            print(f"\n📨 서버 메시지 수신:")
            print(f"   데이터: {data}")
        
        @self.sio.on('stt_result')
        async def on_stt_result(data):
            print(f"\n" + "="*60)
            print(f"📝 STT 결과 수신!")
            print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   타입: {data.get('type', 'unknown')}")
            print(f"   텍스트: {data.get('text', 'N/A')}")
            print(f"   신뢰도: {data.get('confidence', 'N/A')}")
            if 'session_id' in data:
                print(f"   세션 ID: {data.get('session_id')}")
            print("="*60)
        
        @self.sio.on('embedding_result')
        async def on_embedding_result(data):
            print(f"\n🧠 임베딩 결과 수신:")
            print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   차원: {data.get('dimension', 'N/A')}")
            if 'embedding' in data:
                embedding = data['embedding']
                print(f"   임베딩 길이: {len(embedding)}")
                print(f"   임베딩 샘플: {embedding[:5]}...")
        
        @self.sio.on('clarify_turn')
        async def on_clarify_turn(data):
            print(f"\n❓ Clarify 턴 수신:")
            print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   세션 ID: {data.get('session_id', 'N/A')}")
            print(f"   턴 ID: {data.get('turn_id', 'N/A')}")
            print(f"   질문: {data.get('question', 'N/A')}")
            print(f"   상태: {data.get('status', 'N/A')}")
        
        @self.sio.on('final_answer')
        async def on_final_answer(data):
            print(f"\n✅ 최종 답변 수신:")
            print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   세션 ID: {data.get('session_id', 'N/A')}")
            print(f"   답변: {data.get('answer', 'N/A')[:100]}...")
            if 'audio_url' in data:
                print(f"   오디오 URL: {data.get('audio_url')}")
        
        @self.sio.on('stop_streaming_stt')
        async def on_stop_streaming_stt(data):
            print(f"\n🛑 스트리밍 STT 중지 신호 수신:")
            print(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   세션 ID: {data.get('session_id', 'N/A')}")
        
        @self.sio.event
        async def connect_error(data):
            print(f"\n❌ Socket.IO 연결 오류:")
            print(f"   에러: {data}")
    
    async def connect(self):
        """Socket.IO 서버 연결"""
        try:
            print(f"\n📡 Socket.IO 서버 연결 시도: {self.url}")
            await self.sio.connect(self.url)
            return True
        except Exception as e:
            print(f"❌ 연결 실패: {e}")
            return False
    
    async def disconnect(self):
        """Socket.IO 서버 연결 종료"""
        await self.sio.disconnect()
    
    async def wait(self):
        """연결 유지 및 이벤트 대기"""
        print("\n" + "="*60)
        print("👂 이벤트 수신 대기 중...")
        print("   (Ctrl+C로 종료)")
        print("="*60)
        
        try:
            await self.sio.wait()
        except KeyboardInterrupt:
            print("\n\n🛑 종료 요청 수신")


async def main():
    parser = argparse.ArgumentParser(description='Socket.IO 연결 테스트')
    parser.add_argument('--socketio-url', type=str,
                       default='http://localhost:5000',
                       help='Socket.IO 서버 URL')
    
    args = parser.parse_args()
    
    client = SocketIOTestClient(args.socketio_url)
    
    # 연결 시도
    connected = await client.connect()
    if not connected:
        print("\n❌ Socket.IO 서버 연결 실패!")
        sys.exit(1)
    
    # 이벤트 수신 대기
    try:
        await client.wait()
    except KeyboardInterrupt:
        print("\n\n🛑 종료 중...")
    finally:
        await client.disconnect()
        print("\n✅ 테스트 종료")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 프로그램 종료")

