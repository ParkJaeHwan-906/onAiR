"""
STT 테스트 스크립트 (음성 파일 사용)

음성 파일을 사용하여 버퍼링 STT와 스트리밍 STT가 정상 동작하고
Socket.IO로 잘 전송되는지 테스트합니다.

사용 방법:
    python tests/test_stt_with_audio_file.py --mode buffered --audio audio.wav
    python tests/test_stt_with_audio_file.py --mode streaming --audio audio.wav
"""
import asyncio
import sys
import os
import argparse
import wave
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from stt.gcp_stt_buffered import GcpBufferedStt
from stt.gcp_stt_stream import GcpStreamingStt
from stt.socketio_client import SocketIOClient
from server.websocket_manager import ConnectionManager


class AudioFileStream:
    """음성 파일을 마이크 스트림처럼 시뮬레이션하는 클래스"""
    def __init__(self, audio_file_path: str, rate: int = 16000, channels: int = 1):
        self.audio_file_path = audio_file_path
        self.rate = rate
        self.channels = channels
        self.stream = None
        self.chunk_size = int(rate * 0.1)  # 100ms 청크
        
    def start(self):
        """WAV 파일 열기"""
        if not os.path.exists(self.audio_file_path):
            raise FileNotFoundError(f"음성 파일을 찾을 수 없습니다: {self.audio_file_path}")
        
        self.stream = wave.open(self.audio_file_path, 'rb')
        
        # 파일 속성 확인
        file_rate = self.stream.getframerate()
        file_channels = self.stream.getnchannels()
        file_sample_width = self.stream.getsampwidth()
        
        print(f"📄 음성 파일 정보:")
        print(f"   파일: {self.audio_file_path}")
        print(f"   샘플레이트: {file_rate} Hz")
        print(f"   채널: {file_channels}")
        print(f"   샘플 폭: {file_sample_width} bytes")
        
        # 샘플레이트 불일치 시 경고
        if file_rate != self.rate:
            print(f"⚠️ 경고: 파일 샘플레이트({file_rate})와 설정값({self.rate})이 다릅니다.")
        
        # 스테레오를 모노로 변환해야 하는 경우
        if file_channels != self.channels:
            print(f"⚠️ 경고: 파일 채널({file_channels})과 설정값({self.channels})이 다릅니다.")
        
        # 16비트 PCM이 아닌 경우 경고
        if file_sample_width != 2:
            print(f"⚠️ 경고: 16비트 PCM이 아닙니다 (현재: {file_sample_width * 8}비트)")
    
    def read(self):
        """마이크에서 읽은 것처럼 음성 청크 반환"""
        if not self.stream:
            return None
        
        # 지정된 크기만큼 읽기 (1600 샘플 = 100ms @ 16kHz)
        chunk = self.stream.readframes(self.chunk_size)
        
        if not chunk:
            return None
        
        # 스테레오를 모노로 변환 (필요한 경우)
        if self.stream.getnchannels() == 2:
            import numpy as np
            audio_data = np.frombuffer(chunk, dtype=np.int16)
            audio_data = audio_data.reshape(-1, 2)
            audio_data = audio_data.mean(axis=1).astype(np.int16)
            chunk = audio_data.tobytes()
        
        return chunk
    
    def pause(self):
        """일시 정지 (마이크 시뮬레이션)"""
        pass
    
    def resume(self):
        """재개 (마이크 시뮬레이션)"""
        pass
    
    def stop(self):
        """파일 닫기"""
        if self.stream:
            self.stream.close()
            self.stream = None
    
    def is_active(self):
        """스트림 활성 상태 확인"""
        return self.stream is not None


async def test_buffered_stt(audio_file: str, socketio_url: str):
    """버퍼링 STT 테스트"""
    print("\n" + "="*60)
    print("🔵 버퍼링 STT 테스트 시작")
    print("="*60)
    
    # 연결 관리자 및 Socket.IO 클라이언트 초기화
    manager = ConnectionManager()
    socketio_client = SocketIOClient(manager=manager)
    manager.set_socketio_client(socketio_client)
    
    # Socket.IO 서버 연결
    print(f"\n📡 Socket.IO 서버 연결 중: {socketio_url}")
    connected = await socketio_client.connect()
    if not connected:
        print("❌ Socket.IO 서버 연결 실패!")
        return False
    
    print("✅ Socket.IO 서버 연결 성공")
    
    # 음성 파일 스트림 생성
    audio_stream = AudioFileStream(audio_file)
    audio_stream.start()
    
    # 버퍼링 STT 인스턴스 생성
    buffered_stt = GcpBufferedStt()
    
    # 브로드캐스트 함수 (Socket.IO로 전송)
    async def broadcaster(msg):
        print(f"\n📤 STT 결과 전송:")
        print(f"   타입: {msg.get('type')}")
        print(f"   텍스트: {msg.get('text')}")
        print(f"   신뢰도: {msg.get('confidence', 'N/A')}")
        
        # Socket.IO로 전송
        await manager.broadcast(msg)
        print("   ✅ Socket.IO 전송 완료")
    
    try:
        # 버퍼링 STT 실행
        print(f"\n🎤 버퍼링 STT 처리 시작...")
        await buffered_stt.run(audio_stream, broadcaster)
        
        print("\n✅ 버퍼링 STT 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"\n❌ 버퍼링 STT 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        audio_stream.stop()
        await socketio_client.disconnect()


async def test_streaming_stt(audio_file: str, socketio_url: str):
    """스트리밍 STT 테스트"""
    print("\n" + "="*60)
    print("🟢 스트리밍 STT 테스트 시작")
    print("="*60)
    
    # 연결 관리자 및 Socket.IO 클라이언트 초기화
    manager = ConnectionManager()
    socketio_client = SocketIOClient(manager=manager)
    manager.set_socketio_client(socketio_client)
    
    # Socket.IO 서버 연결
    print(f"\n📡 Socket.IO 서버 연결 중: {socketio_url}")
    connected = await socketio_client.connect()
    if not connected:
        print("❌ Socket.IO 서버 연결 실패!")
        return False
    
    print("✅ Socket.IO 서버 연결 성공")
    
    # 음성 파일 스트림 생성
    audio_stream = AudioFileStream(audio_file)
    audio_stream.start()
    
    # 스트리밍 STT 인스턴스 생성
    streaming_stt = GcpStreamingStt(socketio_client=socketio_client)
    
    # 세션 ID 생성
    import uuid
    session_id = str(uuid.uuid4())
    print(f"\n🆔 세션 ID: {session_id}")
    
    # 브로드캐스트 함수 (호환성을 위해 유지)
    async def broadcaster(msg):
        pass  # 스트리밍 STT는 내부에서 Socket.IO로 직접 전송
    
    try:
        # 스트리밍 STT 실행
        print(f"\n🎤 스트리밍 STT 처리 시작...")
        print("   (실시간으로 중간 결과와 최종 결과가 표시됩니다)")
        
        # 비동기로 실행
        await streaming_stt.run(audio_stream, broadcaster=broadcaster, session_id=session_id)
        
        print("\n✅ 스트리밍 STT 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"\n❌ 스트리밍 STT 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        audio_stream.stop()
        await socketio_client.disconnect()


async def main():
    parser = argparse.ArgumentParser(description='STT 테스트 스크립트 (음성 파일 사용)')
    parser.add_argument('--mode', choices=['buffered', 'streaming'], required=True,
                       help='테스트할 STT 모드')
    parser.add_argument('--audio', type=str, required=True,
                       help='테스트할 음성 파일 경로 (WAV 파일)')
    parser.add_argument('--socketio-url', type=str,
                       default='http://localhost:5000',
                       help='Socket.IO 서버 URL')
    
    args = parser.parse_args()
    
    # 음성 파일 존재 확인
    if not os.path.exists(args.audio):
        print(f"❌ 음성 파일을 찾을 수 없습니다: {args.audio}")
        return
    
    # 테스트 실행
    if args.mode == 'buffered':
        success = await test_buffered_stt(args.audio, args.socketio_url)
    else:
        success = await test_streaming_stt(args.audio, args.socketio_url)
    
    if success:
        print("\n🎉 모든 테스트 성공!")
        sys.exit(0)
    else:
        print("\n❌ 테스트 실패!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

