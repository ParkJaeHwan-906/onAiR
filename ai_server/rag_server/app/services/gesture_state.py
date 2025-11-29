from app.services.gesture_service import process_gesture

class GestureManager:
    def __init__(self, default_rect):
        self.enabled = False
        self.button_rect = default_rect

        self.waiting_for_start = False
        self.waiting_for_end = False

    def reset_to_initial_state(self):
        self.enabled = False
        self.waiting_for_start = False
        self.waiting_for_end = False

    async def handle_frame(self, frame, on_start, on_end):
        if not self.enabled:
            # 디버깅: enabled가 False인 경우 로그 출력 (처음 몇 번만 출력)
            if not hasattr(self, '_disabled_log_count'):
                self._disabled_log_count = 0
            if self._disabled_log_count < 3:  # 처음 3번만 로그 출력
                print(f"🔍 [Gesture Debug] 제스처 인식 비활성화 상태 (enabled=False) - 프레임은 수신 중이지만 MediaPipe 실행 안 됨")
                self._disabled_log_count += 1
            return

        # 프레임 크기 가져오기
        frame_h, frame_w = frame.shape[:2]
        
        # 버튼 좌표를 기준 해상도(1920x1080)에서 실제 프레임 해상도로 변환
        # 버튼 좌표는 1920x1080 기준으로 하드코딩되어 있음
        REFERENCE_WIDTH = 1920
        REFERENCE_HEIGHT = 1080
        
        # 비율 계산하여 좌표 변환
        scale_x = frame_w / REFERENCE_WIDTH
        scale_y = frame_h / REFERENCE_HEIGHT
        
        left = int(self.button_rect[0] * scale_x)
        top = int(self.button_rect[1] * scale_y)
        right = int(self.button_rect[2] * scale_x)
        bottom = int(self.button_rect[3] * scale_y)
        
        # 디버깅: 프레임 크기와 변환된 버튼 좌표 출력 (처음 몇 번만)
        if not hasattr(self, '_coord_log_count'):
            self._coord_log_count = 0
        if self._coord_log_count < 3:
            print(f"🔍 [Gesture Debug] 프레임 크기: {frame_w}x{frame_h}, 원본 버튼 좌표: {self.button_rect}, 변환된 좌표: ({left}, {top}, {right}, {bottom})")
            self._coord_log_count += 1

        result = process_gesture(frame, self.button_rect)
        if not result:
            return

        finger_x = result["x"]
        finger_y = result["y"]

        # 디버깅: 프레임 크기 및 좌표 정보 출력
        if finger_x % 50 == 0 or finger_y % 50 == 0:  # 로그 스팸 방지
            print(f"🔍 [Gesture Debug] 프레임 크기: ({frame_w}, {frame_h}), 검지 좌표: ({finger_x}, {finger_y}), 버튼 영역: ({left}, {top}, {right}, {bottom})")

        inside = (left <= finger_x <= right and top <= finger_y <= bottom)

        # 디버깅: 제스처 감지 및 좌표 정보 출력
        if inside:
            print(f"🔍 [Gesture Debug] 검지 좌표: ({finger_x}, {finger_y}), 버튼 영역: ({left}, {top}, {right}, {bottom}), inside: {inside}")
            print(f"🔍 [Gesture Debug] waiting_for_start: {self.waiting_for_start}, waiting_for_end: {self.waiting_for_end}")

        if not inside:
            return

        # 종료 버튼 클릭 체크
        if self.waiting_for_end:
            print("=" * 80)
            print("✅ [Gesture] 서비스 종료 버튼 클릭 이벤트 발생")
            print(f"   검지 좌표: ({finger_x}, {finger_y})")
            print(f"   버튼 영역: ({left}, {top}, {right}, {bottom})")
            print("=" * 80)
            self.waiting_for_end = False
            await on_end()
            return

        # 시작 버튼 클릭 체크
        if self.waiting_for_start:
            print("=" * 80)
            print("✅ [Gesture] 서비스 시작 버튼 클릭 이벤트 발생")
            print(f"   검지 좌표: ({finger_x}, {finger_y})")
            print(f"   버튼 영역: ({left}, {top}, {right}, {bottom})")
            print("=" * 80)
            self.waiting_for_start = False
            await on_start()
            return
