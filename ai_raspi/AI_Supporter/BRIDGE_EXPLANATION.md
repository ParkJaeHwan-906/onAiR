# 브리지(Bridge) 구조 설명

## 브리지란?

**브리지 = HTTP 서버 + HTTP 클라이언트 조합**

Python 3.10 프로세스와 Python 3.13 프로세스 간 통신을 위한 **다리 역할**을 합니다.

## 구성 요소

### 1. 브리지 서버 (HTTP 서버)
**파일:** `bridge/stt_bridge_server.py`  
**실행 위치:** Python 3.10 프로세스 내부  
**기술:** Flask (HTTP 서버)

```python
# 브리지 서버의 핵심 기능

# 1. STT 결과 수신 (Python 3.10에서 호출)
@app.route('/stt/result', methods=['POST'])
def receive_stt_result():
    # STT 결과를 메모리 큐에 저장
    stt_results_queue.append(data)

# 2. STT 결과 제공 (Python 3.13에서 호출)
@app.route('/stt/poll', methods=['GET'])
def poll_stt_result():
    # 큐에서 STT 결과를 꺼내서 반환
    result = stt_results_queue.pop(0)
    return result
```

### 2. 브리지 클라이언트 (HTTP 클라이언트)
**파일:** `bridge/stt_bridge_client.py`  
**실행 위치:** Python 3.13 프로세스 내부  
**기술:** aiohttp (비동기 HTTP 클라이언트)

```python
# 브리지 클라이언트의 핵심 기능

async def poll_stt_results(self):
    # 브리지 서버에 HTTP GET 요청
    async with session.get(f"{self.bridge_url}/stt/poll") as response:
        data = await response.json()
        
        if data.get("has_result"):
            result = data["result"]
            # Socket.IO 클라이언트로 전송
            await self.socketio_client.emit_stt_result(result)
```

## 통신 흐름

```
┌─────────────────────────────────────────────────────────────┐
│ Python 3.10 프로세스                                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Wakeword 감지                                            │
│  2. STT 실행 (GCP STT)                                       │
│  3. STT 결과 생성: {"type": "final", "text": "안녕하세요"}   │
│                                                               │
│  ┌─────────────────────────────────────┐                    │
│  │ 브리지 서버 (Flask HTTP 서버)        │                    │
│  │ 포트: 8888                           │                    │
│  │                                      │                    │
│  │ POST /stt/result                    │                    │
│  │ → STT 결과를 메모리 큐에 저장        │                    │
│  │                                      │                    │
│  │ stt_results_queue = [                │                    │
│  │   {"type": "final", "text": "..."}  │                    │
│  │ ]                                    │                    │
│  └─────────────────────────────────────┘                    │
│           ▲                                                  │
│           │ HTTP POST                                        │
│           │                                                  │
│  send_stt_result_to_bridge(stt_data)                         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
           │
           │ HTTP (로컬호스트:8888)
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ Python 3.13 프로세스                                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────┐                    │
│  │ 브리지 클라이언트 (HTTP 클라이언트)  │                    │
│  │                                      │                    │
│  │ GET /stt/poll (0.1초마다 폴링)      │                    │
│  │ ← 큐에서 STT 결과 가져오기           │                    │
│  └─────────────────────────────────────┘                    │
│           │                                                  │
│           │ STT 결과 전달                                    │
│           ▼                                                  │
│  ┌─────────────────────────────────────┐                    │
│  │ Socket.IO 클라이언트                 │                    │
│  │                                      │                    │
│  │ emit_stt_result(result)              │                    │
│  │ → FastAPI 서버로 전송                │                    │
│  └─────────────────────────────────────┘                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## 왜 브리지가 필요한가?

### 문제 상황
- **Python 3.10**: Wakeword 모델이 3.10에서만 동작 → STT도 3.10에서 실행
- **Python 3.13**: Socket.IO 클라이언트가 3.13에서만 동작
- **문제**: 서로 다른 프로세스 간 데이터 전달 필요

### 해결 방법
**브리지 = 프로세스 간 통신 다리**

1. **메모리 공유 불가능** (서로 다른 프로세스)
2. **HTTP 통신 사용** (로컬호스트)
   - 브리지 서버: STT 결과를 받아서 큐에 저장
   - 브리지 클라이언트: 큐에서 결과를 가져와서 Socket.IO로 전송

## 브리지의 핵심 역할

### 1. 데이터 버퍼링
```python
# 브리지 서버 내부
stt_results_queue = []  # 메모리 큐

# Python 3.10에서 STT 결과 전송
stt_results_queue.append({"type": "final", "text": "안녕하세요"})

# Python 3.13에서 STT 결과 수신
result = stt_results_queue.pop(0)  # 큐에서 꺼내기
```

### 2. 프로세스 간 통신
- **HTTP POST**: Python 3.10 → 브리지 서버 (STT 결과 전송)
- **HTTP GET**: 브리지 서버 → Python 3.13 (STT 결과 수신)

### 3. 비동기 처리
- 브리지 클라이언트가 0.1초마다 폴링하여 실시간성 유지
- Socket.IO 클라이언트와 비동기로 통합

## 요약

**브리지 = HTTP 서버 + HTTP 클라이언트**

- **브리지 서버**: Python 3.10 프로세스 내부에서 실행, STT 결과를 큐에 저장
- **브리지 클라이언트**: Python 3.13 프로세스 내부에서 실행, 큐에서 결과를 가져와서 Socket.IO로 전송

이렇게 해서 **Python 3.10의 STT 결과를 Python 3.13의 Socket.IO 클라이언트로 전달**할 수 있습니다!

