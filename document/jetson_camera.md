## ✅ 해결 단계 (Windows 기준)

### 1️⃣ GStreamer 설치하기

1. 아래 링크로 들어가서
    
    👉 https://gstreamer.freedesktop.org/download/
    
2. “**Windows 64-bit**”용 인스톨러를 다운로드하세요.
    
    파일 이름 예:
    
    ```
    gstreamer-1.0-msvc-x86_64-1.24.x.msi
    
    ```
    
3. 설치할 때 **“Complete”** (전체 설치) 옵션을 선택합니다.
4. 설치 후 `환경 변수 PATH`에 자동으로 등록되지만,
    
    혹시 모르니 PowerShell 또는 CMD를 새로 열어서 확인:
    
    ```bash
    gst-launch-1.0 --version
    
    ```
    
    → 이렇게 나오면 성공:
    
    ```
    gst-launch-1.0 version 1.24.x
    GStreamer 1.24.x
    
    ```
    

---

### 2️⃣ SSH 터널로 연결 유지한 상태에서 실행

이제 GStreamer가 설치되었으니,

다음 단계를 **노트북(CMD 또는 PowerShell)** 에서 순서대로 실행합니다.

---

### ✅ (1) SSH 포트포워딩으로 Jetson 접속

```bash
ssh -L 5000:localhost:5000 onair@70.12.112.105

```

이 창은 그대로 열어둡니다.

→ Jetson이 `127.0.0.1:5000`에서 내보내는 스트림이

노트북의 `127.0.0.1:5000` 으로 터널링됩니다.

---

### ✅ (2) Jetson 쪽에서 스트리밍 명령 실행

Jetson 터미널(SSH 안쪽)에서:

```bash
gst-launch-1.0 nvarguscamerasrc ! \
"video/x-raw(memory:NVMM),width=640,height=480,framerate=30/1" ! \
nvvidconv ! nvv4l2h264enc ! h264parse ! matroskamux ! \
tcpserversink host=127.0.0.1 port=5000

```

---

### ✅ (3) 이제 노트북에서 영상 받기 (새 터미널 열기)

새로운 **CMD** 또는 **PowerShell** 창을 열고 아래 실행:

```bash
gst-launch-1.0 tcpclientsrc host=127.0.0.1 port=5000 ! ^
matroskademux ! h264parse ! avdec_h264 ! autovideosink sync=false

```

> ⚠️ PowerShell에서는 \ 대신 ^를 써야 줄바꿈이 동작합니다.
> 

---

### 💡 참고 — 실행 중 확인할 것

- Jetson 터미널에
    
    ```
    New client connected
    
    ```
    
    가 뜨면 연결 성공입니다.
    
- 노트북에서 영상 창이 뜨면 끝!

---

## ✅ 빠른 점검 요약표

| 항목 | 설명 | 명령어 |
| --- | --- | --- |
| GStreamer 설치 확인 | 버전 표시되면 OK | `gst-launch-1.0 --version` |
| SSH 터널 연결 | Jetson과 포트포워딩 | `ssh -L 5000:localhost:5000 onair@70.12.112.105` |
| Jetson 스트리밍 | 카메라 인코딩 + TCP 송출 | `gst-launch-1.0 nvarguscamerasrc ... tcpserversink` |
| 노트북 수신 | 스트림 받아서 디코딩 | `gst-launch-1.0 tcpclientsrc ... autovideosink` |

---
