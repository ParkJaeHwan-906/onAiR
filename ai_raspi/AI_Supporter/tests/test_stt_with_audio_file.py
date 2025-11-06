"""
STT 테스트 스크립트 (음성 파일 사용)

음성 파일을 사용하여 버퍼링 STT와 스트리밍 STT가 정상 동작하고
Socket.IO로 잘 전송되는지 테스트합니다.

사용 방법:
    python tests/test_stt_with_audio_file.py --mode buffered --audio audio.wav
    python tests/test_stt_with_audio_file.py --mode streaming --audio audio.wav
"""
import sys
import os
# Windows에서 UTF-8 인코딩 설정
if sys.platform == 'win32':
    try:
        import codecs
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass  # 인코딩 설정 실패 시 그대로 진행

import asyncio
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
from config import settings


class AudioFileStream:
    """음성 파일을 마이크 스트림처럼 시뮬레이션하는 클래스"""
    def __init__(self, audio_file_path: str, rate: int = 16000, channels: int = 1, streaming_mode: bool = False):
        self.audio_file_path = audio_file_path
        self.rate = rate
        self.channels = channels
        self.stream = None
        self.chunk_size = int(rate * 0.1)  # 100ms 청크
        self.streaming_mode = streaming_mode  # 스트리밍 모드 (실시간 시뮬레이션)
        self.chunk_duration = 0.1  # 100ms
        self.last_read_time = None  # 마지막 읽기 시간
        
    def start(self):
        """WAV 파일 열기"""
        if not os.path.exists(self.audio_file_path):
            raise FileNotFoundError(f"음성 파일을 찾을 수 없습니다: {self.audio_file_path}")
        
        self.stream = wave.open(self.audio_file_path, 'rb')
        
        # 파일 속성 확인
        file_rate = self.stream.getframerate()
        file_channels = self.stream.getnchannels()
        file_sample_width = self.stream.getsampwidth()
        total_frames = self.stream.getnframes()
        
        print(f"📄 음성 파일 정보:")
        print(f"   파일: {self.audio_file_path}")
        print(f"   샘플레이트: {file_rate} Hz")
        print(f"   채널: {file_channels}")
        print(f"   샘플 폭: {file_sample_width} bytes")
        print(f"   총 프레임: {total_frames} ({total_frames / file_rate:.2f}초)")
        
        if self.streaming_mode:
            print(f"   🎤 스트리밍 모드: 실시간 시뮬레이션 (청크 간격: {self.chunk_duration*1000:.0f}ms)")
        
        # 샘플레이트 불일치 시 경고
        if file_rate != self.rate:
            print(f"⚠️ 경고: 파일 샘플레이트({file_rate})와 설정값({self.rate})이 다릅니다.")
        
        # 스테레오를 모노로 변환해야 하는 경우
        if file_channels != self.channels:
            print(f"⚠️ 경고: 파일 채널({file_channels})과 설정값({self.channels})이 다릅니다.")
        
        # 16비트 PCM이 아닌 경우 경고
        if file_sample_width != 2:
            print(f"⚠️ 경고: 16비트 PCM이 아닙니다 (현재: {file_sample_width * 8}비트)")
        
        # 음성 시작 위치 찾기 (조용한 부분 건너뛰기) - 버퍼링 모드에서만
        if not self.streaming_mode and total_frames > 0:
            import struct
            # 현재 위치 저장
            current_pos = self.stream.tell()
            self.stream.rewind()
            
            # 처음 1000 프레임 읽어서 음성 시작 위치 찾기
            search_frames = min(1000, total_frames)
            test_data = self.stream.readframes(search_frames)
            
            if len(test_data) >= 2:
                samples = [struct.unpack('<h', test_data[i:i+2])[0] for i in range(0, len(test_data)-1, 2)]
                # 0이 아닌 샘플 찾기 (임계값: 절댓값이 100 이상)
                threshold = 100
                for i, sample in enumerate(samples):
                    if abs(sample) >= threshold:
                        start_time = i / file_rate
                        print(f"🔊 음성 시작 위치: 약 {start_time:.2f}초 (프레임 {i})")
                        # 음성 시작 위치로 이동
                        self.stream.rewind()
                        self.stream.setpos(i)
                        break
                else:
                    # 음성 시작 위치를 찾지 못한 경우 처음으로 되돌리기
                    print(f"⚠️ 음성 시작 위치를 찾지 못했습니다. 처음부터 읽습니다.")
                    self.stream.rewind()
        
        # 스트리밍 모드: 시간 추적 시작
        if self.streaming_mode:
            import time
            self.last_read_time = time.time()
    
    def read(self):
        """마이크에서 읽은 것처럼 음성 청크 반환"""
        if not self.stream:
            return None
        
        # 스트리밍 모드: 실시간 시뮬레이션 (청크 간격만큼 대기)
        if self.streaming_mode and self.last_read_time is not None:
            import time
            elapsed = time.time() - self.last_read_time
            sleep_time = self.chunk_duration - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            self.last_read_time = time.time()
        
        # 지정된 크기만큼 읽기 (1600 샘플 = 100ms @ 16kHz)
        chunk = self.stream.readframes(self.chunk_size)
        
        if not chunk:
            # 파일 끝에 도달
            if not self.streaming_mode:
                print(f"📄 음성 파일 읽기 완료 (파일 끝)")
            return None
        
        # 스테레오를 모노로 변환 (필요한 경우)
        if self.stream.getnchannels() == 2:
            import numpy as np
            audio_data = np.frombuffer(chunk, dtype=np.int16)
            audio_data = audio_data.reshape(-1, 2)
            audio_data = audio_data.mean(axis=1).astype(np.int16)
            chunk = audio_data.tobytes()
        
        return chunk
    
    def rewind(self):
        """파일을 처음으로 되돌리기"""
        if self.stream:
            self.stream.rewind()
    
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


async def test_buffered_stt(audio_file: str, socketio_url: str, buffer_duration: float = None):
    """버퍼링 STT 테스트"""
    print("\n" + "="*60)
    print("🔵 버퍼링 STT 테스트 시작")
    print("="*60)
    
    # 버퍼링 시간 설정 (기본값: 설정 파일의 값)
    if buffer_duration is not None:
        settings.STT_BUFFER_DURATION_SEC = buffer_duration
        print(f"⚙️ 버퍼링 시간 설정: {buffer_duration}초")
    
    # 연결 관리자 및 Socket.IO 클라이언트 초기화
    manager = ConnectionManager()
    socketio_client = SocketIOClient(manager=manager)
    # 테스트용 URL 설정
    socketio_client.server_url = socketio_url
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
    # 테스트용 URL 설정
    socketio_client.server_url = socketio_url
    manager.set_socketio_client(socketio_client)
    
    # Socket.IO 서버 연결
    print(f"\n📡 Socket.IO 서버 연결 중: {socketio_url}")
    connected = await socketio_client.connect()
    if not connected:
        print("❌ Socket.IO 서버 연결 실패!")
        return False
    
    print("✅ Socket.IO 서버 연결 성공")
    
    # 음성 파일 스트림 생성 (스트리밍 모드: 실시간 시뮬레이션)
    audio_stream = AudioFileStream(audio_file, streaming_mode=True)
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
    parser.add_argument('--buffer-duration', type=float,
                       default=None,
                       help='버퍼링 시간 (초). 기본값: 설정 파일의 값')
    
    args = parser.parse_args()
    
    # 음성 파일 존재 확인
    if not os.path.exists(args.audio):
        print(f"❌ 음성 파일을 찾을 수 없습니다: {args.audio}")
        return
    
    # 테스트 실행
    if args.mode == 'buffered':
        success = await test_buffered_stt(args.audio, args.socketio_url, args.buffer_duration)
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

