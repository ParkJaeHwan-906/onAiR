# 🎤 통신 음성 테스트 가이드

## 📋 테스트 전 확인사항

1. **FastAPI 서버가 실행 중인지 확인**
   - 서버 URL: `https://onair.ai.kr` (또는 설정된 서버 주소)
   - Socket.IO 경로: `/ws`

2. **마이크 장치가 연결되어 있는지 확인**
   ```bash
   # 마이크 장치 목록 확인
   python3 -c "import sounddevice as sd; print(sd.query_devices())"
   ```

---

## 🚀 실행 순서

### 1단계: 별도 프로세스 실행 (WebRTC 오디오/비디오 스트리밍)

**터미널 1**에서 실행:

```bash
cd raspi/app/sockets
python3 socket_manager.py
```

**예상 출력**:
```
🔌 Connecting to https://onair.ai.kr/ws ...
✅ Connected to EC2 server
🎙️ Starting microphone stream...  # handle_audio_stream 이벤트 수신 시
```

**역할**:
- FastAPI 서버에 Socket.IO로 연결
- `register_device` 이벤트로 "raspi" 디바이스 등록
- 비디오 스트리밍 자동 시작
- `handle_audio_stream` 이벤트 수신 시 오디오 스트리밍 시작

---

### 2단계: FastAPI 서버에서 이벤트 전송 (테스트용)

**FastAPI 서버 터미널** 또는 **웹 브라우저 콘솔**에서:

#### 방법 1: FastAPI 서버 로그 확인
- 별도 프로세스가 연결되면 다음과 같은 로그가 나타남:
  ```
  🔗 [디바이스 등록] Registered device: raspi (sid...)
  📊 현재 연결된 디바이스: ['raspi'] (총 1개)
  ```

#### 방법 2: 웹에서 통신 요청 (실제 시나리오)
1. 웹에서 모바일로 통신 요청
2. 모바일에서 통신 수락
3. 모바일 → FastAPI: `accept_communication` 이벤트
4. FastAPI → 라즈베리파이: `handle_audio_stream` 이벤트 (start: True)

---

## 🧪 테스트 시나리오

### 시나리오 1: 직접 이벤트 전송 테스트 (개발용)

**FastAPI 서버 터미널**에서 Python 스크립트로 테스트:

```python
# test_audio_stream.py
import socketio
import asyncio

sio = socketio.AsyncClient()

@sio.event
async def connect():
    print("✅ Connected to FastAPI server")
    # 라즈베리파이로 handle_audio_stream 이벤트 전송
    await sio.emit("handle_audio_stream", {"start": True}, to="raspi")
    print("📤 handle_audio_stream 이벤트 전송 완료")

@sio.event
async def disconnect():
    print("❌ Disconnected")

async def main():
    await sio.connect("https://onair.ai.kr", socketio_path="/ws")
    await sio.wait()

if __name__ == "__main__":
    asyncio.run(main())
```

**실행**:
```bash
python3 test_audio_stream.py
```

**예상 결과**:
- 라즈베리파이 터미널: `🎙️ Audio streaming start signal received from server`
- 라즈베리파이 터미널: `🎙️ Starting microphone stream...`
- FastAPI 서버: `audio_frame` 이벤트 수신 (바이너리 오디오 데이터)

---

### 시나리오 2: 전체 통신 플로우 테스트

#### 2-1. 초기 설정

**터미널 1**: 별도 프로세스 실행
```bash
cd raspi/app/sockets
python3 socket_manager.py
```

**터미널 2**: Python 3.10 프로세스 실행 (선택사항, STT 테스트용)
```bash
cd ai_raspi/AI_Supporter
python3.10 main_py310.py
```

**터미널 3**: Python 3.13 프로세스 실행 (선택사항, STT 테스트용)
```bash
cd ai_raspi/AI_Supporter
python3.13 main.py
```

#### 2-2. 웹에서 통신 요청

1. **웹 브라우저**에서 모바일로 통신 요청 버튼 클릭
2. **모바일 앱**에서 통신 수락
3. **모바일 앱** → FastAPI: `accept_communication` 이벤트 전송

#### 2-3. 확인 사항

**라즈베리파이 터미널 1** (별도 프로세스):
```
🎙️ Audio streaming start signal received from server
🎙️ Starting microphone stream...
```

**FastAPI 서버 터미널**:
```
[DEBUG] accept_communication 이벤트 발생
📞 통신 요청 수락: AI_Supporter/OPERATOR 기능 중지 및 WebRTC 오디오 스트리밍 시작
[DEBUG] handle_audio_stream(True) 이벤트 emit (WebRTC 오디오 스트리밍 목적)
```

**웹 브라우저**:
- 오디오 스트림 수신 확인 (WebRTC 연결)

---

### 시나리오 3: 오디오 스트리밍 중지 테스트

**웹 브라우저**에서 통신 종료 버튼 클릭

**예상 결과**:
- **라즈베리파이 터미널 1**:
  ```
  🛑 Audio streaming stop signal received from server
  🛑 Stopping microphone stream...
  🔇 Microphone stream closed
  ```

- **FastAPI 서버 터미널**:
  ```
  [DEBUG] communication_close 이벤트 발생
  [DEBUG] wakeword_start_waiting 이벤트 emit
  ```

---

## 🔍 문제 해결

### 문제 1: 연결 실패

**증상**:
```
⚠️ Connection failed: ...
```

**해결 방법**:
1. FastAPI 서버가 실행 중인지 확인
2. 서버 URL 확인 (`raspi/app/sockets/socket_manager.py`의 `SERVER_URL`)
3. 네트워크 연결 확인

---

### 문제 2: 마이크 장치를 찾을 수 없음

**증상**:
```
⚠️ Audio stream error: ...
```

**해결 방법**:
```bash
# 마이크 장치 확인
python3 -c "import sounddevice as sd; print(sd.query_devices())"

# 기본 입력 장치 확인
python3 -c "import sounddevice as sd; print(sd.default.device)"
```

**설정 파일 확인**:
- `raspi/app/sockets/socket_manager.py`에서 `AudioService` 초기화 부분 확인
- 필요시 `device` 파라미터 추가

---

### 문제 3: 오디오 프레임이 전송되지 않음

**확인 사항**:
1. `handle_audio_stream` 이벤트가 수신되었는지 확인
2. FastAPI 서버에서 `audio_frame` 이벤트가 수신되는지 확인
3. 마이크가 실제로 오디오를 수집하는지 확인

**디버깅**:
```python
# raspi/app/sockets/socket_manager.py의 stream_audio 함수에 로그 추가
def stream_audio(self):
    def callback(indata, frames, time_info, status):
        if not self.is_streaming: return
        print(f"📊 오디오 데이터 수집: {len(indata)} frames")  # 디버깅용
        # ... 기존 코드
```

---

### 문제 4: 디바이스 등록 실패

**증상**:
- FastAPI 서버에서 "raspi" 디바이스가 등록되지 않음

**확인 사항**:
1. `register_device` 이벤트가 전송되었는지 확인
2. FastAPI 서버의 `device_map`에 "raspi"가 있는지 확인
3. Socket.IO 연결이 정상인지 확인

---

## 📊 성공적인 테스트 확인 포인트

### ✅ 정상 동작 시 나타나는 로그

**라즈베리파이 터미널**:
```
✅ Connected to EC2 server
🎙️ Audio streaming start signal received from server
🎙️ Starting microphone stream...
```

**FastAPI 서버 터미널**:
```
🔗 [디바이스 등록] Registered device: raspi (sid...)
📊 현재 연결된 디바이스: ['raspi'] (총 1개)
[DEBUG] audio_frame 이벤트 수신됨  # 지속적으로 수신
```

**웹 브라우저**:
- 오디오 스트림이 정상적으로 재생됨
- WebRTC 연결이 정상적으로 유지됨

---

## 🎯 빠른 테스트 체크리스트

- [ ] FastAPI 서버 실행 중
- [ ] 라즈베리파이에서 `python3 socket_manager.py` 실행
- [ ] FastAPI 서버에서 "raspi" 디바이스 등록 확인
- [ ] `handle_audio_stream` 이벤트 전송 (start: True)
- [ ] 라즈베리파이에서 오디오 스트리밍 시작 확인
- [ ] FastAPI 서버에서 `audio_frame` 이벤트 수신 확인
- [ ] 웹에서 오디오 스트림 재생 확인
- [ ] `handle_audio_stream` 이벤트 전송 (start: False)
- [ ] 라즈베리파이에서 오디오 스트리밍 중지 확인

---

## 💡 추가 팁

1. **백그라운드 실행**:
   ```bash
   nohup python3 socket_manager.py > socket_manager.log 2>&1 &
   ```

2. **로그 확인**:
   ```bash
   tail -f socket_manager.log
   ```

3. **프로세스 종료**:
   ```bash
   pkill -f socket_manager.py
   ```

4. **포트 확인**:
   ```bash
   netstat -tuln | grep 5050  # 브리지 서버 포트 (Python 3.10)
   ```

