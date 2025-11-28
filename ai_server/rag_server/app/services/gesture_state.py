# app/services/gesture_state.py

from app.services.gesture_service import process_gesture

class GestureManager:
    def __init__(self, default_rect):
        self.enabled = False
        self.button_rect = default_rect

        self.waiting_for_start = False
        self.waiting_for_end = False

    def reset_to_initial_state(self):
        """제스처 인식 상태 초기화"""
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
        inside = (left <= finger_x <= right) and (top <= finger_y <= bottom)

        # END 버튼 모드인지 확인
        if result["is_end_button"]:
            if self.waiting_for_end and inside:
                print("[Gesture] END detected")
                self.waiting_for_end = False
                await on_end()
            return

        # START 감지
        if self.waiting_for_start and inside:
            print("[Gesture] START detected")
            self.waiting_for_start = False
            await on_start()
            return
