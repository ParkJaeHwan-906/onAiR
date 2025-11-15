"""
WebRTC 오디오 스트리밍 모듈
마이크에서 오디오를 읽어 Socket.IO를 통해 모바일로 전송합니다.
"""
import time
import threading
import logging
import queue
import asyncio
import sounddevice as sd
import numpy as np
import base64

logger = logging.getLogger(__name__)

class AudioStreamer:
    """
    WebRTC 오디오 스트리밍 클래스
    sounddevice를 사용하여 마이크에서 오디오를 읽고 Socket.IO로 전송합니다.
    """
    def __init__(self, socketio_client, sample_rate=16000, channels=1, chunk_size=1024):
        """
        Args:
            socketio_client: SocketIOClient 인스턴스 (오디오 프레임 전송용)
            sample_rate: 샘플레이트 (기본값: 16000Hz)
            channels: 채널 수 (기본값: 1, 모노)
            chunk_size: 청크 크기 (기본값: 1024 샘플)
        """
        self.socketio_client = socketio_client
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        
        self.is_streaming = False
        self.stream = None
        self.stream_thread = None
        self.stop_event = threading.Event()
        self.audio_queue = queue.Queue(maxsize=10)  # 오디오 프레임 큐 (백프레셔 방지)
        self.send_thread = None  # 오디오 전송 스레드
        
        logger.info("🎙️ AudioStreamer 초기화 완료")
        logger.info(f"   - Sample Rate: {self.sample_rate}Hz")
        logger.info(f"   - Channels: {self.channels}")
        logger.info(f"   - Chunk Size: {self.chunk_size} samples")
    
    def start(self):
        """오디오 스트리밍 시작"""
        if self.is_streaming:
            logger.warning("⚠️ 오디오 스트리밍이 이미 실행 중입니다.")
            return
        
        try:
            logger.info("=" * 60)
            logger.info("🎙️ 오디오 스트리밍 시작")
            logger.info("=" * 60)
            
            # sounddevice InputStream 생성
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.chunk_size,
                dtype='float32',
                callback=self._audio_callback
            )
            
            self.is_streaming = True
            self.stop_event.clear()
            
            # 스트림 시작
            self.stream.start()
            
            # 오디오 전송 스레드 시작
            self.send_thread = threading.Thread(target=self._send_audio_loop, daemon=True)
            self.send_thread.start()
            
            logger.info("✅ 오디오 스트림 시작 완료")
            logger.info("   - 마이크에서 오디오 읽기 시작")
            logger.info("   - Socket.IO로 audio_frame 이벤트 전송 시작")
            
        except Exception as e:
            logger.error(f"❌ 오디오 스트리밍 시작 실패: {e}")
            self.is_streaming = False
            raise
    
    def stop(self):
        """오디오 스트리밍 중지"""
        if not self.is_streaming:
            logger.warning("⚠️ 오디오 스트리밍이 실행 중이 아닙니다.")
            return
        
        try:
            logger.info("=" * 60)
            logger.info("🛑 오디오 스트리밍 중지")
            logger.info("=" * 60)
            
            self.is_streaming = False
            self.stop_event.set()
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            # 오디오 전송 스레드 종료 대기
            if self.send_thread and self.send_thread.is_alive():
                self.send_thread.join(timeout=1.0)
            
            # 큐 비우기
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
            
            logger.info("✅ 오디오 스트림 중지 완료")
            
        except Exception as e:
            logger.error(f"❌ 오디오 스트리밍 중지 실패: {e}")
    
    def _audio_callback(self, indata, frames, time_info, status):
        """
        sounddevice 오디오 콜백 함수
        마이크에서 오디오 데이터를 받을 때마다 호출됩니다.
        
        Args:
            indata: 입력 오디오 데이터 (numpy array)
            frames: 프레임 수
            time_info: 타임스탬프 정보
            status: 상태 정보
        """
        if status:
            logger.warning(f"⚠️ 오디오 스트림 상태: {status}")
        
        if not self.is_streaming:
            return
        
        try:
            # 오디오 데이터를 float32에서 int16으로 변환
            # sounddevice는 기본적으로 float32(-1.0 ~ 1.0)로 반환
            audio_int16 = (indata * 32767).astype(np.int16)
            
            # 오디오 데이터를 base64로 인코딩
            audio_bytes = audio_int16.tobytes()
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # 타임스탬프 생성 (밀리초)
            timestamp = int(time.time() * 1000)
            
            # 오디오 프레임을 큐에 추가 (백프레셔 방지를 위해 큐가 가득 차면 스킵)
            try:
                self.audio_queue.put_nowait({
                    "timestamp": timestamp,
                    "audio": audio_base64,
                    "sample_rate": self.sample_rate,
                    "channels": self.channels
                })
            except queue.Full:
                # 큐가 가득 차면 가장 오래된 프레임 제거 후 추가
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.put_nowait({
                        "timestamp": timestamp,
                        "audio": audio_base64,
                        "sample_rate": self.sample_rate,
                        "channels": self.channels
                    })
                except queue.Empty:
                    pass
    
    def _send_audio_loop(self):
        """오디오 프레임 전송 루프 (별도 스레드에서 실행)"""
        logger.info("🚀 오디오 전송 스레드 시작")
        
        while self.is_streaming or not self.audio_queue.empty():
            try:
                # 큐에서 오디오 프레임 가져오기 (타임아웃: 0.1초)
                try:
                    audio_data = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Socket.IO로 audio_frame 이벤트 전송
                if self.socketio_client and self.socketio_client.sio:
                    try:
                        # 이벤트 루프 가져오기
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            # 이벤트 루프가 없으면 새로 생성
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        if loop.is_running():
                            # 이미 실행 중인 루프면 태스크로 추가
                            asyncio.run_coroutine_threadsafe(
                                self._emit_audio_frame(audio_data),
                                loop
                            )
                        else:
                            # 루프가 실행 중이 아니면 직접 실행
                            loop.run_until_complete(
                                self._emit_audio_frame(audio_data)
                            )
                    except Exception as e:
                        logger.error(f"❌ audio_frame 이벤트 전송 실패: {e}")
                
            except Exception as e:
                logger.error(f"❌ 오디오 전송 루프 오류: {e}")
                if not self.is_streaming:
                    break
        
        logger.info("🔚 오디오 전송 스레드 종료")
    
    async def _emit_audio_frame(self, audio_data):
        """비동기 audio_frame 이벤트 전송"""
        try:
            await self.socketio_client.sio.emit(
                "audio_frame",
                audio_data
            )
        except Exception as e:
            logger.error(f"❌ audio_frame emit 오류: {e}")

