# 🏗️ 라즈베리파이 아키텍처 및 마이크 음성 데이터 흐름

## 📌 전체 구조 개요

라즈베리파이에는 **3개의 독립적인 Python 프로세스**가 실행됩니다:

1. **Python 3.10 프로세스** (`ai_raspi/AI_Supporter/main_py310.py`)
2. **Python 3.13 프로세스** (`ai_raspi/AI_Supporter/main.py`)
3. **별도 프로세스** (`raspi/app/sockets/socket_manager.py`) - Python 버전 불명확

---

## 🔧 프로세스별 역할 및 시작 방법

### 1. Python 3.10 프로세스

**파일**: `ai_raspi/AI_Supporter/main_py310.py`

**시작 방법**:
```bash
cd ai_raspi/AI_Supporter
python3.10 main_py310.py
```

**역할**:
- ✅ **Wakeword 감지** (Python 3.10에서만 동작)
- ✅ **버퍼링 STT 실행** (GCP STT)
- ✅ **스트리밍 STT 실행** (GCP STT)
- ✅ **브리지 서버 실행** (포트 5050, Socket.IO 서버)
- ✅ **STT 결과를 브리지 서버로 전송**

**마이크 사용**:
- `MicStream` 클래스 사용
- STT 목적으로만 사용 (Wakeword 감지, 버퍼링/스트리밍 STT)

**브리지 서버**:
- Socket.IO 서버 (포트 5050)
- Python 3.13의 브리지 클라이언트가 연결하여 STT 결과를 수신

---

### 2. Python 3.13 프로세스

**파일**: `ai_raspi/AI_Supporter/main.py`

**시작 방법**:
```bash
cd ai_raspi/AI_Supporter
python3.13 main.py
```

**역할**:
- ✅ **Socket.IO 클라이언트 실행** (FastAPI 서버와 통신)
- ✅ **브리지 클라이언트 실행** (Python 3.10 브리지 서버에서 STT 결과 수신)
- ✅ **STT 결과를 Socket.IO로 FastAPI 서버에 전송**
- ✅ **FastAPI 서버로부터 이벤트 수신** (cv_detection_failed, start_streaming_stt, mic_off, mic_on, wakeword_start_waiting 등)

**마이크 사용**:
- ❌ **마이크를 직접 사용하지 않음**
- STT는 Python 3.10 프로세스에서 처리됨
- 브리지 클라이언트를 통해 Python 3.10에서 STT 결과를 수신

---

### 3. 별도 프로세스 (WebRTC 오디오/비디오 스트리밍)

**파일**: `raspi/app/sockets/socket_manager.py`

**시작 방법**:
```bash
cd raspi/app/sockets
python3 socket_manager.py
# 또는
python3 -m app.sockets.socket_manager
```

**역할**:
- ✅ **WebRTC 오디오 스트리밍** (`AudioService` 클래스)
- ✅ **비디오 스트리밍** (`CameraService` 클래스)
- ✅ **FastAPI 서버로 직접 연결** (브리지 서버를 거치지 않음)

**마이크 사용**:
- `AudioService` 클래스 사용
- WebRTC 오디오 스트리밍 목적으로만 사용
- **Python 3.10/3.13 프로세스와 독립적으로 실행**
- FastAPI 서버로 직접 `audio_frame` 이벤트 전송

---

## 🎤 마이크 음성 데이터 흐름

### 케이스 1: STT 목적 (Wakeword, 버퍼링/스트리밍 STT)

```
[물리적 마이크]
    ↓
[Python 3.10 프로세스]
├─ MicStream.start()
├─ 마이크 음성 수집
├─ Wakeword 감지 (콜백)
└─ 버퍼링/스트리밍 STT 실행
    ↓
[Python 3.10 프로세스]
├─ STT 결과 생성 (텍스트)
└─ 브리지 서버로 전송
    ↓
[브리지 서버] (포트 5050, Socket.IO)
├─ Python 3.10 프로세스 내부에서 실행
└─ STT 결과 저장 (메모리 큐)
    ↓
[Python 3.13 프로세스]
├─ 브리지 클라이언트가 브리지 서버에 연결
├─ STT 결과 폴링 (Socket.IO)
└─ STT 결과 수신
    ↓
[Python 3.13 프로세스]
└─ Socket.IO 클라이언트를 통해 FastAPI 서버로 전송
    ↓
[FastAPI 서버]
└─ stt_result 이벤트 수신
```

**요약**: 
- 마이크 → Python 3.10 → 브리지 서버 → Python 3.13 → FastAPI
- **브리지 서버를 반드시 거쳐야 함**

---

### 케이스 2: WebRTC 오디오 스트리밍 목적

```
[물리적 마이크]
    ↓
[별도 프로세스] (raspi/app/sockets/socket_manager.py)
├─ AudioService.start_streaming()
├─ 마이크 음성 수집 (sd.InputStream)
└─ audio_frame 이벤트로 FastAPI 서버에 직접 전송
    ↓
[FastAPI 서버]
└─ audio_frame 이벤트 수신 → 웹으로 전송
```

**요약**:
- 마이크 → 별도 프로세스 → FastAPI (직접 연결)
- **브리지 서버를 거치지 않음**
- **Python 3.10/3.13 프로세스와 독립적**

---

## 🔄 프로세스 간 통신 구조

### Python 3.10 ↔ Python 3.13 통신

```
[Python 3.10]
├─ 브리지 서버 (Socket.IO 서버, 포트 5050)
│   └─ STT 결과 저장 및 전송
│
[Python 3.13]
└─ 브리지 클라이언트 (Socket.IO 클라이언트)
    └─ 브리지 서버에 연결하여 STT 결과 수신
```

**통신 방식**: Socket.IO (로컬호스트 127.0.0.1:5050)

**데이터**:
- STT 결과 (텍스트)
- Wakeword 감지 이벤트
- 마이크 제어 이벤트 (mic_off, mic_on)
- Wakeword 제어 이벤트 (wakeword_start_waiting)

---

### Python 3.13 ↔ FastAPI 서버 통신

```
[Python 3.13]
├─ Socket.IO 클라이언트
│   └─ FastAPI 서버에 연결
│
[FastAPI 서버]
└─ Socket.IO 서버
    └─ 이벤트 수신 및 전송
```

**통신 방식**: Socket.IO (원격 서버)

**데이터**:
- STT 결과 (텍스트)
- 이벤트 수신: cv_detection_failed, start_streaming_stt, stop_streaming_stt, mic_off, mic_on, wakeword_start_waiting 등

---

### 별도 프로세스 ↔ FastAPI 서버 통신

```
[별도 프로세스] (raspi/app/sockets/socket_manager.py)
├─ Socket.IO 클라이언트
│   └─ FastAPI 서버에 직접 연결
│
[FastAPI 서버]
└─ Socket.IO 서버
    └─ 이벤트 수신 및 전송
```

**통신 방식**: Socket.IO (원격 서버)

**데이터**:
- `audio_frame` (바이너리 오디오 데이터)
- `video_frame` (비디오 프레임)
- 이벤트 수신: handle_audio_stream, video_stream 등

---

## 📊 프로세스별 마이크 접근 요약

| 프로세스 | 마이크 사용 | 목적 | 브리지 서버 경유 |
|---------|-----------|------|----------------|
| **Python 3.10** | ✅ `MicStream` | STT 목적 (Wakeword, 버퍼링/스트리밍 STT) | ✅ 필수 |
| **Python 3.13** | ❌ 사용 안 함 | STT 결과를 FastAPI로 전송만 담당 | ✅ 필수 |
| **별도 프로세스** | ✅ `AudioService` | WebRTC 오디오 스트리밍 | ❌ 직접 연결 |

---

## 🔑 핵심 포인트

1. **마이크는 하나**이지만, **두 개의 독립적인 스트림**이 동시에 열릴 수 있음:
   - `MicStream` (Python 3.10): STT 목적
   - `AudioService` (별도 프로세스): WebRTC 오디오 스트리밍 목적

2. **STT 목적 음성 데이터**는 반드시 브리지 서버를 거쳐야 함:
   - Python 3.10 → 브리지 서버 → Python 3.13 → FastAPI

3. **WebRTC 오디오 스트리밍 목적 음성 데이터**는 브리지 서버를 거치지 않음:
   - 별도 프로세스 → FastAPI (직접 연결)

4. **Python 3.10 프로세스 시작**:
   - 수동 실행: `python3.10 main_py310.py`
   - systemd 서비스 파일은 없음 (직접 실행 필요)

5. **Python 3.13 프로세스 시작**:
   - 수동 실행: `python3.13 main.py`
   - systemd 서비스 파일은 없음 (직접 실행 필요)

6. **별도 프로세스 시작**:
   - 수동 실행: `python3 socket_manager.py`
   - 또는 FastAPI 앱 시작 시 자동 실행 (raspi/app/main.py)

---

## 🚀 실행 순서 권장사항

1. **Python 3.10 프로세스 시작** (브리지 서버 포함)
   ```bash
   cd ai_raspi/AI_Supporter
   python3.10 main_py310.py
   ```

2. **Python 3.13 프로세스 시작** (브리지 클라이언트 포함)
   ```bash
   cd ai_raspi/AI_Supporter
   python3.13 main.py
   ```

3. **별도 프로세스 시작** (WebRTC 오디오/비디오 스트리밍)
   ```bash
   cd raspi/app/sockets
   python3 socket_manager.py
   ```

---

## ⚠️ 주의사항

1. **마이크 장치 충돌 가능성**:
   - `MicStream`과 `AudioService`가 동시에 같은 마이크 장치를 사용할 수 있음
   - sounddevice 라이브러리는 동시에 여러 스트림을 열 수 있지만, 일부 마이크 장치는 단일 스트림만 지원할 수 있음

2. **프로세스 독립성**:
   - Python 3.10, Python 3.13, 별도 프로세스는 완전히 독립적으로 실행됨
   - 하나가 종료되어도 다른 프로세스는 계속 실행됨

3. **브리지 서버 의존성**:
   - Python 3.13 프로세스는 Python 3.10 프로세스의 브리지 서버에 연결해야 STT 결과를 받을 수 있음
   - Python 3.10 프로세스가 종료되면 STT 기능이 중단됨

