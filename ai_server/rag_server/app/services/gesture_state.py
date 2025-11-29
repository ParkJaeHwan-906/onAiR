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

        result = process_gesture(frame, self.button_rect)
        if not result:
            return

        finger_x = result["x"]
        finger_y = result["y"]

        left, top, right, bottom = self.button_rect
        inside = (left <= finger_x <= right and top <= finger_y <= bottom)

        if not inside:
            return

        # 종료 버튼 클릭 체크
        if self.waiting_for_end:
            print("✅ [Gesture] 서비스 종료 버튼 클릭 감지")
            self.waiting_for_end = False
            await on_end()
            return

        # 시작 버튼 클릭 체크
        if self.waiting_for_start:
            print("✅ [Gesture] 서비스 시작 버튼 클릭 감지")
            self.waiting_for_start = False
            await on_start()
            return
