import threading
import asyncio


class AudioModeManager:
    def __init__(self, mic, audio_streamer):
        self.mode = "STT"
        self.lock = threading.Lock()

        self.mic = mic
        self.audio_streamer = audio_streamer
        self.socketio_client = None
        self.stt_core = None 

        self.is_rtc_running = False
        
        self.wakeword_count = 0
        self.socket_ready = threading.Event()

    # ---------------------------------------------
    # SocketIO 준비 이벤트
    # ---------------------------------------------
    def set_socket_ready(self):
        """SocketIO 연결 완료 시 호출"""
        self.socket_ready.set()

    def wait_for_socket_ready(self):
        """STTCore에서 필요 시 소켓 준비될 때까지 대기"""
        self.socket_ready.wait()

    # ---------------------------------------------
    # 모드 확인
    # ---------------------------------------------
    def is_stt_mode(self):
        return self.mode == "STT"

    def is_rtc_mode(self):
        return self.mode == "RTC"

    # ---------------------------------------------
    # STT 모드 전환
    # ---------------------------------------------
    def switch_to_stt(self):
        with self.lock:
            if self.mode == "STT":
                return

            self.mode = "STT"
            self.is_rtc_running = False

            # RTC 종료
            if self.audio_streamer:
                self.audio_streamer.stop()

            # 마이크 점유
            self.mic.acquire()

    # ---------------------------------------------
    # RTC 모드 전환
    # ---------------------------------------------
    def switch_to_rtc(self):
        with self.lock:
            if self.mode == "RTC":
                return

            self.mode = "RTC"
            self.is_rtc_running = True

            # 마이크 장치 해제(STT 종료)
            self.mic.release()

            # RTC 오디오 스트리밍 시작
            if self.audio_streamer:
                self.audio_streamer.start()

    # ---------------------------------------------
    # Wakeword 감지 시 FastAPI로 이벤트 전송
    # ---------------------------------------------
    def on_wakeword_detected(self):
        """
        구조:
        STTCore.run() → wakeword 감지 → manager.on_wakeword_detected()

        → socket_ready 가 True 일 때만 이벤트 전송
        """

        if not self.socket_ready.is_set() or not self.socketio_client:
            return

        # 연결 상태 확인
        if not self.socketio_client.is_connected():
            return

        try:
            loop = self.socketio_client.loop
            if loop is None:
                # loop이 아직 설정되지 않았으면 새로 생성하여 사용
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # 새 루프에서 직접 실행
                loop.run_until_complete(self.socketio_client.emit_wakeword_detected())
            else:
                # loop이 있으면 thread-safe로 실행
                future = asyncio.run_coroutine_threadsafe(
                self.socketio_client.emit_wakeword_detected(),
                loop
            )
                # 결과 대기 (타임아웃 설정)
                try:
                    future.result(timeout=5.0)
                except Exception as e:
                    print(f"❌ wakeword_detected 이벤트 전송 타임아웃: {e}")

        except Exception as e:
            print(f"❌ wakeword_detected Error: {e}")
            import traceback
            traceback.print_exc()

    # ---------------------------------------------
    # ai_supporter 이벤트 전송
    # ---------------------------------------------
    def on_ai_supporter(self):
        """
        구조:
        STTCore.run() → wakeword 감지 → manager.on_ai_supporter()

        → socket_ready 가 True 일 때만 이벤트 전송
        """

        if not self.socket_ready.is_set() or not self.socketio_client:
            return

        # 연결 상태 확인
        if not self.socketio_client.is_connected():
            return

        try:
            loop = self.socketio_client.loop
            if loop is None:
                return

            asyncio.run_coroutine_threadsafe(
                self.socketio_client.emit_ai_support(),
                loop
            )

        except Exception as e:
            print(f"❌ on_ai_supporter Error: {e}")

    def on_connect_operator(self):
        """
        구조:
        STTCore.run() → wakeword 감지 → manager.on_connect_operator()

        → socket_ready 가 True 일 때만 이벤트 전송
        """

        if not self.socket_ready.is_set() or not self.socketio_client:
            return

        # 연결 상태 확인
        if not self.socketio_client.is_connected():
            return

        try:
            loop = self.socketio_client.loop
            if loop is None:
                return

            asyncio.run_coroutine_threadsafe(
                self.socketio_client.emit_connect_operator(),
                loop
            )

        except Exception as e:
            print(f"❌ on_connect_operator Error: {e}")