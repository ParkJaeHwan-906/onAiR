# 🔄 프로세스 통합 계획

## 📊 현재 구조

### 현재 3개 프로세스

1. **Python 3.10 프로세스** (`ai_raspi/AI_Supporter/main_py310.py`)
   - Wakeword 감지
   - 버퍼링/스트리밍 STT
   - 브리지 서버 (포트 5050)

2. **Python 3.13 프로세스** (`ai_raspi/AI_Supporter/main.py`)
   - Socket.IO 클라이언트 (비동기, FastAPI 서버)
   - 브리지 클라이언트 (동기, Python 3.10 브리지 서버)

3. **별도 프로세스** (`raspi/app/sockets/socket_manager.py`)
   - Python 3.13 실행
   - Socket.IO 클라이언트 (동기, FastAPI 서버)
   - WebRTC 오디오/비디오 스트리밍

---

## 🎯 통합 목표

**2개 프로세스로 축소**:
1. **Python 3.10 프로세스**: Wakeword, STT, 브리지 서버
2. **통합 프로세스** (Python 3.13): FastAPI Socket.IO 클라이언트, 브리지 클라이언트, WebRTC 오디오/비디오 스트리밍

---

## ⚠️ 기술적 고려사항

### 문제점

1. **Socket.IO 클라이언트 타입 차이**:
   - 별도 프로세스: `socketio.Client` (동기)
   - Python 3.13 프로세스: `socketio.AsyncClient` (비동기)

2. **브리지 클라이언트 의존성**:
   - 브리지 클라이언트는 `SocketIOClient` (비동기)를 주입받아야 함
   - 하지만 별도 프로세스는 동기 클라이언트 사용

3. **이벤트 핸들러 충돌**:
   - 두 프로세스 모두 `register_device`로 "raspi" 등록
   - FastAPI 서버에서 같은 디바이스가 중복 등록될 수 있음

---

## 💡 통합 방안

### 방안 1: 별도 프로세스를 비동기로 변경 (권장)

**장점**:
- SocketIOClient와 브리지 클라이언트를 모두 통합 가능
- 하나의 Socket.IO 연결로 모든 통신 처리
- 디바이스 중복 등록 문제 해결

**단점**:
- 기존 동기 코드를 비동기로 변경 필요
- 오디오/비디오 스트리밍 로직 수정 필요

**구현 방법**:
1. `raspi/app/sockets/socket_manager.py`를 비동기로 변경
2. `socketio.Client` → `socketio.AsyncClient`로 변경
3. `SocketIOClient` 클래스 통합
4. `SttBridgeClient` 통합
5. 오디오/비디오 스트리밍을 비동기로 처리

---

### 방안 2: 별도 프로세스에 비동기 클라이언트 추가 (하이브리드)

**장점**:
- 기존 동기 코드 유지
- 점진적 통합 가능

**단점**:
- 두 개의 Socket.IO 연결 (동기 + 비동기)
- 디바이스 중복 등록 문제 여전히 존재
- 복잡도 증가

**구현 방법**:
1. 별도 프로세스에 비동기 Socket.IO 클라이언트 추가
2. 동기 클라이언트는 오디오/비디오 스트리밍 전용
3. 비동기 클라이언트는 STT 결과 전송 및 이벤트 수신 전용

---

## 🚀 권장 구현: 방안 1

### 단계별 구현 계획

#### 1단계: 별도 프로세스를 비동기로 변경

**파일**: `raspi/app/sockets/socket_manager.py`

**변경 사항**:
```python
# 기존 (동기)
import socketio
sio = socketio.Client(...)

# 변경 (비동기)
import socketio
import asyncio
sio = socketio.AsyncClient(...)
```

#### 2단계: SocketIOClient 통합

**변경 사항**:
- `ai_raspi/AI_Supporter/stt/socketio_client.py`의 `SocketIOClient` 클래스를 별도 프로세스에 통합
- 또는 별도 프로세스에서 `SocketIOClient` 인스턴스 생성

#### 3단계: 브리지 클라이언트 통합

**변경 사항**:
- `SttBridgeClient` 인스턴스 생성
- `SocketIOClient`를 브리지 클라이언트에 주입
- 브리지 클라이언트 연결 시작

#### 4단계: 오디오/비디오 스트리밍 비동기 처리

**변경 사항**:
- `AudioService`와 `CameraService`를 비동기로 처리
- 스트리밍 루프를 `asyncio`로 변경

---

## 📝 통합 후 구조

### 통합 프로세스 (Python 3.13)

**파일**: `raspi/app/sockets/socket_manager.py` (수정됨)

**역할**:
- ✅ Socket.IO 클라이언트 (비동기, FastAPI 서버)
- ✅ 브리지 클라이언트 (Python 3.10 브리지 서버)
- ✅ WebRTC 오디오/비디오 스트리밍
- ✅ FastAPI 서버로 STT 결과 전송
- ✅ FastAPI 서버로부터 이벤트 수신 (cv_detection_failed, start_streaming_stt, mic_off, mic_on, wakeword_start_waiting 등)

**실행 방법**:
```bash
cd raspi/app/sockets
python3.13 socket_manager.py
```

---

### Python 3.10 프로세스 (변경 없음)

**파일**: `ai_raspi/AI_Supporter/main_py310.py`

**역할**:
- ✅ Wakeword 감지
- ✅ 버퍼링/스트리밍 STT
- ✅ 브리지 서버 (포트 5050)

**실행 방법**:
```bash
cd ai_raspi/AI_Supporter
python3.10 main_py310.py
```

---

## ✅ 통합의 장점

1. **프로세스 수 감소**: 3개 → 2개
2. **디바이스 중복 등록 해결**: 하나의 Socket.IO 연결로 통합
3. **코드 중복 제거**: Socket.IO 클라이언트 로직 통합
4. **유지보수 용이**: 하나의 프로세스에서 모든 FastAPI 통신 관리
5. **리소스 효율**: 프로세스 수 감소로 메모리/CPU 사용량 감소

---

## ⚠️ 주의사항

1. **비동기 전환**: 기존 동기 코드를 비동기로 변경해야 함
2. **이벤트 루프 관리**: `asyncio` 이벤트 루프와 스레드 관리 주의
3. **오디오/비디오 스트리밍**: 비동기 환경에서도 정상 동작하도록 수정 필요
4. **테스트**: 통합 후 전체 플로우 테스트 필수

---

## 🔄 마이그레이션 체크리스트

- [ ] 별도 프로세스를 비동기로 변경
- [ ] SocketIOClient 통합
- [ ] 브리지 클라이언트 통합
- [ ] 오디오/비디오 스트리밍 비동기 처리
- [ ] 이벤트 핸들러 통합
- [ ] 디바이스 등록 로직 통합
- [ ] Python 3.13 프로세스 제거 (`ai_raspi/AI_Supporter/main.py`)
- [ ] 문서 업데이트
- [ ] 전체 플로우 테스트

