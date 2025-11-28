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

        if result["is_end_button"]:
            if self.waiting_for_end and inside:
                print("[Gesture] END detected")
                self.waiting_for_end = False
                await on_end()
            return

        if self.waiting_for_start and inside:
            print("[Gesture] START detected")
            self.waiting_for_start = False
            await on_start()
            return
