# 🔍 Socket.IO 이벤트 전달 문제 점검 체크리스트

## ✅ 수정 완료 사항

### 1. FastAPI 서버 (`socket_handler.py`)
- ✅ `broadcast_to()` 함수 디버깅 로그 활성화
- ✅ `handle_register_device()` 디버깅 로그 활성화
- ✅ `handle_connect()` 연결 정보 상세 로그 추가
- ✅ `handle_wakeword_detected()` 디버깅 로그 추가
- ✅ `handle_stt_result()` 디버깅 로그 추가
- ✅ `handle_wakeword_audio_completed()` 디버깅 로그 추가
- ✅ `handle_intent_audio_completed()` 디버깅 로그 추가

### 2. 모바일 앱 (`SocketIoSttClient.kt`)
- ✅ 연결 성공 시 상세 로그 추가
- ✅ 연결 상태 확인 로그 추가 (5초 후)

### 3. SSE Repository (`SSERepository.kt`)
- ✅ JSON 파싱 오류 수정 (문자열 데이터 스킵)

---

## 🔍 점검해야 할 사항

### 1. 디바이스 등록 확인

**FastAPI 서버 로그에서 확인:**
```
🔗 [디바이스 등록] Registered device: raspi (sid=...)
🔗 [디바이스 등록] Registered device: mobile (sid=...)
📊 현재 연결된 디바이스: ['raspi', 'mobile'] (총 2개)
```

**문제가 있다면:**
- `register_device` 이벤트가 전송되지 않음
- `device_map`에 디바이스가 등록되지 않음

**확인 방법:**
- 라즈베리파이: `SocketIOClient._setup_handlers()`에서 `register_device` 이벤트 전송 확인
- 모바일: `SocketIoSttClient.registerDevice()` 함수 호출 확인

### 2. 이벤트 수신 확인

**각 이벤트 핸들러에서 확인:**
```
🔔 [이벤트 수신] wakeword_detected 이벤트 도착
   SID: ...
   현재 device_map: {...}
   발신자 디바이스: raspi
```

**문제가 있다면:**
- 이벤트가 도착하지 않음
- `device_map`에 발신자가 등록되지 않음

### 3. broadcast_to 함수 동작 확인

**로그에서 확인:**
```
🔍 [broadcast_to] 디버깅: 요청 디바이스=['mobile'], 이벤트=wakeword_detected
   현재 device_map: {...}
   현재 연결된 디바이스 타입: ['raspi', 'mobile']
✅ [broadcast_to] 찾은 디바이스: ['mobile']
📤 [broadcast_to] 이벤트 전송 시도: wakeword_detected → mobile (sid=...)
✅ [broadcast_to] 이벤트 전송 성공: wakeword_detected → mobile (sid=...)
✅ [broadcast_to] 총 1개 디바이스에 이벤트 전송 완료: wakeword_detected → ['mobile']
```

**문제가 있다면:**
- `⚠️ [broadcast_to] 연결된 디바이스가 없습니다.` → `device_map`이 비어있음
- `⚠️ [broadcast_to] Failed to emit to {sid}: {e}` → 연결이 끊어짐

### 4. 브리지 서버 연결 확인

**라즈베리파이 로그에서 확인:**
- 브리지 서버 연결: `✅ STT 브리지 서버(http://127.0.0.1:5050) 연결 성공`
- FastAPI Socket.IO 클라이언트 연결: `✅ Socket.IO 서버 연결 성공`
- 디바이스 등록: `🔗 라즈베리파이 디바이스 등록 요청 전송`

**문제가 있다면:**
- 브리지 서버가 실행되지 않음
- FastAPI Socket.IO 클라이언트가 연결되지 않음

### 5. 모바일 Socket.IO 연결 확인

**모바일 Logcat에서 확인:**
```
✅ Socket.IO 서버 연결 성공: https://onair.ai.kr (경로: /ws)
   Socket ID: ...
📝 [디바이스 등록] register_device 이벤트 전송 시작
✅ [디바이스 등록] register_device 이벤트 전송 완료: mobile
🔍 Socket.IO 연결 상태 확인 (5초 후): ✅ 연결됨
```

**문제가 있다면:**
- `❌ Socket.IO 연결 오류` → 네트워크 문제 또는 서버 접근 불가
- `⚠️ Socket.IO 연결이 안 되어 있습니다.` → 연결 실패

---

## 🐛 일반적인 문제 및 해결 방법

### 문제 1: 디바이스가 등록되지 않음

**증상:**
```
⚠️ [broadcast_to] 연결된 디바이스가 없습니다. 요청: ['mobile'], 현재 연결: []
```

**원인:**
- `register_device` 이벤트가 전송되지 않음
- 연결 후 즉시 이벤트를 전송하려고 해서 연결이 완료되기 전에 전송됨

**해결:**
- 연결 이벤트에서 `registerDevice()` 호출 확인
- 연결 후 약간의 딜레이 추가 (필요시)

### 문제 2: 이벤트가 도착하지 않음

**증상:**
- FastAPI에서 이벤트를 전송했지만 모바일/라즈베리파이에서 수신하지 않음

**원인:**
- 이벤트 핸들러가 등록되지 않음
- `device_map`에 디바이스가 등록되지 않음
- Socket.IO 연결이 끊어짐

**해결:**
- 이벤트 핸들러 등록 확인 (`init_socketio()`)
- `device_map` 상태 확인
- 연결 상태 재확인

### 문제 3: 브리지 서버를 통한 이벤트 전달 실패

**증상:**
- 라즈베리파이 Python 3.10에서 이벤트를 전송했지만 FastAPI에 도착하지 않음

**원인:**
- 브리지 서버가 실행되지 않음
- 브리지 클라이언트가 FastAPI Socket.IO 클라이언트를 주입받지 않음
- 브리지 서버와 클라이언트 간 연결 실패

**해결:**
- 브리지 서버 실행 확인
- `bridge_client.set_fastapi_socketio_client()` 호출 확인
- 브리지 서버 로그 확인

### 문제 4: 모바일에서 이벤트 수신 실패

**증상:**
- FastAPI에서 이벤트를 전송했지만 모바일 Logcat에 로그가 없음

**원인:**
- Socket.IO 연결이 끊어짐
- 이벤트 핸들러가 등록되지 않음
- 네트워크 문제

**해결:**
- 모바일 Logcat에서 연결 상태 확인
- `SocketIoSttClient`의 이벤트 핸들러 등록 확인
- 네트워크 연결 확인

---

## 📊 디버깅 로그 확인 순서

### 1단계: 연결 확인
```
[FastAPI] ✅ [연결] Client connected: ... (from ...)
[FastAPI] 🔗 [디바이스 등록] Registered device: raspi (...)
[FastAPI] 🔗 [디바이스 등록] Registered device: mobile (...)
```

### 2단계: 이벤트 수신 확인
```
[FastAPI] 🔔 [이벤트 수신] wakeword_detected 이벤트 도착
[FastAPI]    발신자 디바이스: raspi
[FastAPI] 📝 [단계 2-1] FastAPI 서버: Wakeword 감지 이벤트 수신 [raspi]
```

### 3단계: 이벤트 전송 확인
```
[FastAPI] 🔍 [broadcast_to] 디버깅: 요청 디바이스=['mobile'], 이벤트=wakeword_detected
[FastAPI] ✅ [broadcast_to] 찾은 디바이스: ['mobile']
[FastAPI] 📤 [broadcast_to] 이벤트 전송 시도: wakeword_detected → mobile
[FastAPI] ✅ [broadcast_to] 이벤트 전송 성공: wakeword_detected → mobile
```

### 4단계: 모바일 수신 확인
```
[모바일] 🔔 [이벤트 수신] wakeword_detected 이벤트 도착!
[모바일] 📩 Wakeword 감지 이벤트 수신: 음성 파일 재생 시작
```

---

## 🔧 추가 디버깅 도구

### FastAPI 서버에서 device_map 상태 확인
```python
# socket_handler.py에 추가
async def handle_get_device_map(sid, data):
    """디바이스 맵 상태 확인 (디버깅용)"""
    print("=" * 60)
    print(f"📊 현재 device_map 상태:")
    print(f"   총 연결 수: {len(device_map)}")
    for sid_key, device in device_map.items():
        print(f"   - {device}: {sid_key[:15]}...")
    print("=" * 60)
    await sio.emit("device_map_status", {"devices": dict(device_map)}, to=sid)
```

### 모바일에서 연결 상태 주기적 확인
```kotlin
// 10초마다 연결 상태 확인
CoroutineScope(Dispatchers.IO).launch {
    while (true) {
        delay(10000)
        val connected = socket?.connected() == true
        Log.i(TAG, "🔍 [주기적 확인] Socket.IO 연결 상태: ${if (connected) "✅ 연결됨" else "❌ 연결 안 됨"}")
    }
}
```

---

## 📝 체크리스트

- [ ] FastAPI 서버가 실행 중인가?
- [ ] 브리지 서버가 실행 중인가? (포트 5050)
- [ ] 라즈베리파이 Python 3.10 프로세스가 실행 중인가?
- [ ] 라즈베리파이 Python 3.13 프로세스가 실행 중인가?
- [ ] 모바일 앱이 실행 중이고 Socket.IO 연결이 되어 있는가?
- [ ] 모든 디바이스가 `register_device` 이벤트를 전송했는가?
- [ ] `device_map`에 모든 디바이스가 등록되어 있는가?
- [ ] 이벤트 핸들러가 모두 등록되어 있는가?
- [ ] 네트워크 연결이 정상인가?

