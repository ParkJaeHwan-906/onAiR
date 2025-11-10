# Python 버전별 실행 가이드

라즈베리파이에서 Python 3.10과 3.13을 함께 사용하는 방법입니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    라즈베리파이                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Python 3.10 프로세스          Python 3.13 프로세스          │
│  ┌─────────────────────┐      ┌─────────────────────┐      │
│  │ - Wakeword 감지     │      │ - Socket.IO 클라이언트│     │
│  │ - STT 실행          │      │ - 브리지 클라이언트   │     │
│  │ - 브리지 서버       │◄─────┤ - FastAPI 서버 통신  │     │
│  │   (포트 8888)      │      │                      │     │
│  └─────────────────────┘      └─────────────────────┘      │
│           │                              │                   │
│           └──────────┬───────────────────┘                  │
│                      │                                      │
│              브리지 서버 (HTTP)                             │
│              (Python 3.10 ↔ 3.13 통신)                      │
└─────────────────────────────────────────────────────────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │   FastAPI 서버       │
            │   (Socket.IO 서버)   │
            └─────────────────────┘
```

## 실행 방법

### 1. Python 3.10 프로세스 실행

```bash
cd ai_raspi/AI_Supporter
python3.10 main_py310.py
```

**역할:**
- Wakeword 감지 (Python 3.10에서만 동작)
- 버퍼링/스트리밍 STT 실행 (Python 3.10에서만 동작)
- 브리지 서버 실행 (포트 8888)
- STT 결과를 브리지 서버로 전송

### 2. Python 3.13 프로세스 실행

```bash
cd ai_raspi/AI_Supporter
python3.13 main.py
```

**역할:**
- Socket.IO 클라이언트 실행 (Python 3.13에서만 동작)
- 브리지 클라이언트 실행 (Python 3.10 브리지 서버에서 STT 결과 폴링)
- STT 결과를 Socket.IO로 FastAPI 서버에 전송

## 통신 흐름

1. **Wakeword 감지** (Python 3.10)
   - `wait_for_wakeword()` → True

2. **버퍼링 STT 실행** (Python 3.10)
   - `GcpBufferedStt.run()` → STT 결과 생성
   - `send_stt_result_to_bridge()` → 브리지 서버로 전송

3. **브리지 서버 수신** (Python 3.10)
   - `/stt/result` 엔드포인트에서 STT 결과 수신
   - 메모리 큐에 저장

4. **브리지 클라이언트 폴링** (Python 3.13)
   - `/stt/poll` 엔드포인트에서 STT 결과 폴링
   - 큐에서 결과 가져오기

5. **Socket.IO 전송** (Python 3.13)
   - `socketio_client.emit_stt_result()` → FastAPI 서버로 전송

## 의존성

### Python 3.10
- `requirements.txt`의 모든 패키지
- 특히: `tflite-runtime==2.14.0` (Wakeword 모델용)

### Python 3.13
- `requirements.txt`의 모든 패키지
- 특히: `python-socketio[asyncio-client]==5.11.3` (Socket.IO 클라이언트용)

## 문제 해결

### 브리지 서버 연결 실패
- Python 3.10 프로세스가 실행 중인지 확인
- 포트 8888이 사용 가능한지 확인: `netstat -an | grep 8888`

### Socket.IO 연결 실패
- Python 3.13 프로세스가 실행 중인지 확인
- FastAPI 서버가 실행 중인지 확인
- `FASTAPI_SERVER_URL` 환경변수 확인

### STT 결과가 전달되지 않음
- 브리지 서버가 실행 중인지 확인
- 브리지 클라이언트가 폴링 중인지 확인
- 로그 확인: Python 3.10과 3.13 프로세스의 로그 모두 확인

