import subprocess
import threading
import base64
import time
import io
from PIL import Image
import numpy as np
import cv2

process = None
thread = None
stop_flag = False

def start_stream(callback):
    global process, thread, stop_flag
    stop_flag = False

    # ✅ H.264 raw 스트림을 stdout 으로 출력
    cmd = [
        "rpicam-vid",
        "--width", "640",
        "--height", "480",
        "--framerate", "10",
        "-t", "0",
        "--codec", "mjpeg",   # jpeg 스트림으로 변경
        "--stdout"
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=4096)

    def read_frames():
        global stop_flag
        buffer = b""
        while not stop_flag:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            buffer += chunk
            # MJPEG에서는 프레임 경계가 0xFFD9 (JPEG 종료)로 구분됨
            while b"\xff\xd9" in buffer:
                frame, buffer = buffer.split(b"\xff\xd9", 1)
                frame += b"\xff\xd9"
                try:
                    b64 = base64.b64encode(frame).decode("utf-8")
                    callback(b64)
                except Exception:
                    continue
        process.stdout.close()

    thread = threading.Thread(target=read_frames, daemon=True)
    thread.start()

def stop_stream():
    global stop_flag, process
    stop_flag = True
    if process:
        process.terminate()
        process = None
    return {"status": "stopped"}
