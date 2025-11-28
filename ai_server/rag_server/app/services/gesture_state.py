# app/services/gesture_state.py
from cgi import print_arguments
from typing import Optional, Tuple
import time
from app.services.gesture_service import process_gesture

class GestureManager:
    def __init__(self, default_rect):
        self.enabled = False
        self.button_rect = default_rect

        self.waiting_for_start= False
        self.waiting_for_end= False

    def update_state_from_mobile(self, visible: bool, rect: Optional[dict] = None):
        """
        모바일에서 보낸 visible/rect 기반으로 제스처 인식 상태 업데이트
        """
        if visible:
            if rect:
                self.button_rect = (
                    rect["left"],
                    rect["top"],
                    rect["right"],
                    rect["bottom"],
                )
            self.enabled = True
            print(f"[Gesture] ON, rect={self.button_rect}")
        else:
            self.enabled = False
            print("[Gesture] OFF")

    async def handle_frame(self, frame, broadcast_to, wait_for_next_step):
        if not self.enabled:
            return

        result=process_gesture(frame, self.button_rect)

        if result == "pointing_inside_button":

            # 시작 버튼 단계
            if self.waiting_for_start:
                print("시작 버튼 클릭 감지")

                # 모바일로 전송
                await broadcast_to("mobile", "service_start_clicked",{})

                #시작 모드 off
                self.waiting_for_start= False

                # mediapipe 종료(버튼 한 번 누르면 끝)
                self.enabled= False
                return
                
            # 종료 버튼 단계
            if self.waiting_for_end:
                print("종료 버튼 클릭 감지")

                await broadcast_to("mobile", "service_end_clicked", {})

                self.waiting_for_end= False
                self.enabled= False
                return  