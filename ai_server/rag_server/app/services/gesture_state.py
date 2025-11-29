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
        
        # 모바일에서 전달한 button_rect를 프레임 크기에 맞춰 변환
        # 모바일 좌표가 상대 좌표(0~1)인 경우를 대비한 변환 로직
        # 현재는 절대 좌표로 가정하지만, 필요시 변환 가능하도록 구조화
        
        # 만약 모바일에서 상대 좌표(0~1)로 전달한다면:
        # left = int(self.button_rect[0] * frame_w)
        # top = int(self.button_rect[1] * frame_h)
        # right = int(self.button_rect[2] * frame_w)
        # bottom = int(self.button_rect[3] * frame_h)
        
        # 현재는 절대 좌표로 가정
        left, top, right, bottom = self.button_rect
        
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
