import socketio
import subprocess
import base64
import threading
import time

sio = socketio.Client()
camera_proc = None
is_streaming = False


def stream_camera():
    global camera_proc, is_streaming

    # rpicam-vid 명령어 구성
    command = [
        "rpicam-vid",
        "--width", "640",
        "--height", "480",
        "--framerate", "20",  
        "--codec", "mjpeg",
        "--inline",
        "--quality", "60",   
        "--flush",             
        "--timeout", "0",
        "-o", "-"
    ]

    print("🎥 Starting rpicam-vid streaming process...")
    # subprocess로 rpicam 실행 (stdout을 파이프로 연결)
    camera_proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )

    buffer = b""
    boundary = b"\xff\xd8"  # JPEG start marker

    while is_streaming and camera_proc and camera_proc.stdout:
        chunk = camera_proc.stdout.read(1024)
        if not chunk:
            break
        buffer += chunk

        # JPEG 프레임 단위로 잘라내기
        while True:
            start_idx = buffer.find(boundary)
            end_idx = buffer.find(b"\xff\xd9", start_idx + 2)
            if start_idx != -1 and end_idx != -1:
                frame = buffer[start_idx:end_idx + 2]
                buffer = buffer[end_idx + 2:]
                frame_b64 = base64.b64encode(frame).decode("utf-8")
                sio.emit("video-frame", {"frame": frame_b64})
            else:
                break

        time.sleep(1 / 15)

    stop_camera()
    print("🛑 Camera stream stopped")


def stop_camera():
    global camera_proc
    if camera_proc:
        try:
            camera_proc.terminate()
            camera_proc.wait(timeout=2)
        except Exception:
            camera_proc.kill()
        camera_proc = None


# === Socket 이벤트 ===
@sio.event
def connect():
    print("✅ Connected to server")
    sio.emit("register_device", {"device": "raspi"})


@sio.event
def disconnect():
    print("❌ Disconnected from server")
    stop_camera()


@sio.on("video_stream")
def on_video_stream(data):
    global is_streaming
    state = data.get("state", "off")
    print(f"📡 Received video_stream: {state}")

    if state == "on" and not is_streaming:
        is_streaming = True
        threading.Thread(target=stream_camera, daemon=True).start()
    elif state == "off" and is_streaming:
        is_streaming = False
        stop_camera()
