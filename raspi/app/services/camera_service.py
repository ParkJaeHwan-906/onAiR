import subprocess
import threading
import base64

process = None
thread = None
stop_flag = False


def start_stream(callback):
    """
    Raspberry Pi Camera V3 스트림을 MJPEG 형태로 읽어 base64로 콜백 전송
    """
    global process, thread, stop_flag
    stop_flag = False

    # ✅ 최신 rpicam-vid 명령 (stdout -> output - 로 변경됨)
    cmd = [
        "rpicam-vid",
        "--width", "640",
        "--height", "480",
        "--framerate", "10",
        "-t", "0",                   # 무제한 스트리밍
        "--codec", "mjpeg",          # MJPEG 형식 (프레임 단위로 구분 가능)
        "--output", "-"              # ✅ 표준 출력(STDOUT)으로 영상 송출
    ]

    # 카메라 프로세스 실행
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=4096)

    def read_frames():
        global stop_flag
        buffer = b""

        while not stop_flag:
            chunk = process.stdout.read(4096)
            if not chunk:
                break

            buffer += chunk

            # MJPEG 프레임은 0xFFD9(JPEG End marker)로 구분됨
            while b"\xff\xd9" in buffer:
                frame, buffer = buffer.split(b"\xff\xd9", 1)
                frame += b"\xff\xd9"

                try:
                    b64 = base64.b64encode(frame).decode("utf-8")
                    callback(b64)   # base64 프레임을 Socket 등으로 전달
                except Exception:
                    continue

        # 프로세스 종료 시 cleanup
        process.stdout.close()

    # 비동기 스레드로 스트림 읽기 시작
    thread = threading.Thread(target=read_frames, daemon=True)
    thread.start()


def stop_stream():
    """
    카메라 프로세스를 안전하게 중단
    """
    global stop_flag, process
    stop_flag = True

    if process:
        process.terminate()
        process = None

    return {"status": "stopped"}
