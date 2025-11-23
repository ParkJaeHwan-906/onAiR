"""
WebRTC 오디오 스트리밍 모듈
마이크에서 오디오를 읽어 Socket.IO를 통해 모바일로 전송합니다.
"""
import time
import threading
import logging
import sounddevice as sd
import numpy as np

logger = logging.getLogger(__name__)

# 재시도 설정
max_retries = 3
retry_delay = 0.5

class AudioStreamer:
    """
    WebRTC 오디오 스트리밍 클래스
    sounddevice를 사용하여 마이크에서 오디오를 읽고 Socket.IO로 전송합니다.
    """
    def __init__(self, socketio_client, sample_rate=16000, channels=1, chunk_size=1024, send_chunk=4):
        """
        Args:
            socketio_client: SocketIOClient 인스턴스 (오디오 프레임 전송용)
            sample_rate: 샘플레이트 (기본값: 16000Hz)
            channels: 채널 수 (기본값: 1, 모노)
            chunk_size: 청크 크기 (기본값: 1024 샘플)
            send_chunk: 전송할 청크 수 (기본값: 4, 버퍼링)
        """
        self.socketio_client = socketio_client
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.send_chunk = send_chunk
        
        self.is_streaming = False       # 현재 스트리밍이 진행중인가에 대한 Flag
        self.stream = None
        self.stream_thread = None
        # 버퍼: 여러 청크를 모아서 한 번에 전송
        self.buffer = np.zeros((chunk_size * send_chunk,), dtype=np.float32)
        self.buffer_index = 0
        
        # [25.11.12] 로그 주석 처리 - 재환
        # logger.info("🎙️ AudioStreamer 초기화 완료")
        # logger.info(f"   - Sample Rate: {self.sample_rate}Hz")
        # logger.info(f"   - Channels: {self.channels}")
        # logger.info(f"   - Chunk Size: {self.chunk_size} samples")
        # logger.info(f"   - Send Chunk: {self.send_chunk} (버퍼 크기: {chunk_size * send_chunk} samples)")
    
    def start(self):
        """오디오 스트리밍 시작"""
        # [25.11.12] 오디오 스트리밍 시작 함수에 대한 try-catch 처리 - 재환
        try:
            if self.is_streaming: # 이미 오디오 스트리밍이 진행중이라면, 중복으로 실행하지 않음
                # [25.11.12] 로그 주석 처리 - 재환
                # logger.warning("⚠️ 오디오 스트리밍이 이미 실행 중입니다.")
                return
            
            # [25.11.12] 로그 주석 처리 - 재환
            # logger.info("=" * 60)
            # logger.info("🎙️ 오디오 스트리밍 시작")
            # logger.info("=" * 60)
            
            self.is_streaming = True
            # 스트리밍 시작 시 버퍼 인덱스 초기화
            self.buffer_index = 0
            
            # 별도 스레드에서 스트리밍 시작
            self.stream_thread = threading.Thread(target=self._stream_audio, daemon=True)
            self.stream_thread.start()
        except Exception as e:
            self.stop()
    
    def stop(self):
        """오디오 스트리밍 종료"""
        if not self.is_streaming:
            # [25.11.12] 로그 주석 처리 - 재환
            # logger.warning("⚠️ 오디오 스트리밍이 실행 중이 아닙니다.")
            return

        # [25.11.12] 로그 주석 처리 - 재환
        # logger.info("=" * 60)
        # logger.info("🛑 오디오 스트리밍 중지")
        # logger.info("=" * 60)
        
        self.is_streaming = False
        
        # 스트림이 열려있으면 명시적으로 닫기
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.warning(f"⚠️ Stream close error: {e}")
            finally:
                self.stream = None
        
        # [25.11.21] 스레드 종료 중복 호출 방지 수정 - 재환 
        # 스트림 스레드 종료 대기
        # if self.stream_thread and self.stream_thread.is_alive():
        #     self.stream_thread.join(timeout=2.0)
        
        current = threading.current_thread()
        if self.stream_thread and self.stream_thread.is_alive():
            # 자신을 join하면 데드락 발생 → join 스킵
            if self.stream_thread is current:
                return

            # 안전하게 join 수행
            try:
                self.stream_thread.join(timeout=2.0)
            except Exception as e:
                logger.warning(f"Thread join error: {e}")

        # [25.11.21] 로그 주석 처리 - 재환 
        # logger.info("✅ 오디오 스트림 중지 완료")

    def _stream_audio(self):
        """오디오 스트리밍 메인 루프 (별도 스레드에서 실행)"""
        # 스트림 시작 시 버퍼 인덱스 초기화
        self.buffer_index = 0
        
        def callback(indata, frames, time_info, status):
            """sounddevice 오디오 콜백 함수"""
            if not self.is_streaming:
                return
            
            if status:
                logger.warning(f"⚠️ 오디오 스트림 상태: {status}")
            
            length = len(indata)
            
            if self.buffer_index + length >= len(self.buffer):
                # 버퍼 채워짐 → 서버로 전송
                self.buffer[self.buffer_index:self.buffer_index+length] = indata[:, 0]
                
                try:
                    timestamp = int(time.time() * 1000)  # 현재 시각 (ms 단위)
                    
                    # 바이너리 데이터로 변환 (float32 → bytes)
                    audio_bytes = self.buffer.tobytes()
                    
                    # Socket.IO로 audio_frame 이벤트 전송
                    if self.socketio_client and self.socketio_client.sio:
                        try:
                            import asyncio
                            try:
                                loop = self.socketio_client.loop
                            except RuntimeError:
                                # 이벤트 루프가 없으면 새로 생성
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            if loop.is_running():
                                # 이미 실행 중인 루프면 태스크로 추가
                                asyncio.run_coroutine_threadsafe(
                                    self._emit_audio_frame(timestamp, audio_bytes),
                                    loop
                                )
                            else:
                                # 루프가 실행 중이 아니면 직접 실행
                                loop.run_until_complete(
                                    self._emit_audio_frame(timestamp, audio_bytes)
                                )
                        except Exception as e:
                            logger.error(f"❌ audio_frame 이벤트 전송 실패: {e}")
                except Exception as e:
                    logger.error(f"⚠️ Audio emit error: {e}")
                
                # 버퍼 인덱스 초기화
                self.buffer_index = 0
            else:
                # 아직 버퍼 채우기
                self.buffer[self.buffer_index:self.buffer_index+length] = indata[:, 0]
                self.buffer_index += length
        
        # 재시도 로직
        for attempt in range(max_retries):
            # is_streaming이 False가 되면 즉시 종료
            if not self.is_streaming:   
                # [25.11.21] 로그 주석 처리 - 재환
                # logger.info("🔇 오디오 스트리밍 중지 신호 수신, 스트림 시작 취소")
                break
            
            try:
                # [25.11.21] 로그 주석 처리 - 재환
                # logger.info(f"🎙️ WebRTC 오디오 스트림 시작 시도 {attempt + 1}/{max_retries}...")
                
                self.stream = sd.InputStream(
                    channels=self.channels,
                    samplerate=self.sample_rate,
                    blocksize=self.chunk_size,
                    callback=callback,
                    dtype='float32',
                    device=None  # 기본 장치 사용 (STT 프로세스가 해제한 후 사용)
                )
                # 오디오 스트림 시작 
                self.stream.start()
                # [25.11.21] 로그 주석 처리 - 재환
                # logger.info("✅ WebRTC 오디오 스트림 시작 성공")
                
                # 스트리밍이 활성화된 동안 대기
                # 0.05초 동안 sleep 
                # -> stop 이벤트를 최대한 실시간으로 감지하기 위해서
                # while self.is_streaming:
                #     time.sleep(0.05)
                # [25.11.21] 로그 주석 처리 - 재환
                # logger.info("🔇 WebRTC 오디오 스트림 종료 (is_streaming=False)")
                # break
                
            except Exception as e:
                if attempt < max_retries - 1:
                    current_delay = retry_delay * (2 ** attempt)  # 지수 백오프
                    continue
                    # [25.11.21] 로그 주석 처리 - 재환
                    # logger.warning(f"   {current_delay}초 후 재시도...")

                else:       # 시도 횟수가 초과되었을 때 바로 탈출
                    self.stop()
                    raise RuntimeError("오디오 스트림 시도 횟수 초과")

                # [25.11.21] 로그 주석 처리 - 재환
                # else:
                #     logger.error("❌ WebRTC 오디오 스트림 시작 실패 (최대 재시도 횟수 초과)")
                #     logger.error(f"   오류: {e}")

            # [25.11.21] finally 제거, try - catch 로 조금 더 명확한 로직 처리 - 재환 
            # finally:
            #     # 스트림 정리
            #     if self.stream is not None:
            #         try:
            #             self.stream.stop()
            #             self.stream.close()
            #             # [25.11.21] 로그 주석 처리 - 재환
            #             # logger.info("🔇 WebRTC 마이크 스트림 닫기 완료")
            #         except Exception as e:
            #             logger.warning(f"⚠️ 스트림 닫기 오류 (무시 가능): {e}")
            #         finally:
            #             self.stream = None

            # [25.11.21] try-catch 문으로 구조 변경하며, 외부 로직 추가 - 재환
            # 현 위치까지 왔다는 것은 try 문을 무사히 통과했다는 의미
            while self.is_streaming:
                time.sleep(0.05)
            
            break   # is_streaming false 임이 감지되었으니, 재연결 시도할 필요 없음

    async def _emit_audio_frame(self, timestamp, frame_bytes):
        """audio_frame 전송 요청을 socket_handler로 전달"""
        if not self.socketio_client:
            return

        try:
            loop = self.socketio_client.loop

            asyncio.run_coroutine_threadsafe(
                self.socketio_client.emit_audio_frame(timestamp, frame_bytes),
                loop
            )
        except Exception as e:
            logger.error(f"❌ audio_frame emit 요청 실패: {e}")
