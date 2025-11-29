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

        result = process_gesture(frame, self.button_rect)
        if not result:
            return

        finger_x = result["x"]
        finger_y = result["y"]

        inside = (left <= finger_x <= right and top <= finger_y <= bottom)

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
