# STT 테스트 가이드

## 개요

이 가이드는 라즈베리파이에서 실행되는 STT 기능을 테스트하는 방법을 설명합니다.

## 테스트 방법

### 1. Socket.IO 연결 테스트 (가장 먼저!)

Socket.IO 서버에 연결되어 STT 결과를 수신할 수 있는지 테스트합니다.

```bash
# 로컬에서 실행 (PC에서 Socket.IO 서버가 실행 중이어야 함)
python tests/test_socketio_connection.py --socketio-url http://localhost:5000

# EC2에서 실행 중인 경우
python tests/test_socketio_connection.py --socketio-url http://<EC2_IP>:5000
```

**이 스크립트는:**
- Socket.IO 서버에 연결
- 디바이스 등록
- `stt_result`, `embedding_result`, `clarify_turn`, `final_answer` 등 모든 이벤트 수신 대기
- 라즈베리파이에서 STT 결과가 전송되면 실시간으로 표시

**테스트 전 확인사항:**
- Socket.IO 서버(`ai_ar/app/sockets/socket_manager.py`)가 실행 중이어야 함
- 포트 5000이 열려있어야 함

---

### 2. 음성 파일을 사용한 STT 테스트

실제 마이크 없이도 음성 파일로 STT 기능을 테스트할 수 있습니다.

#### 2-1. 버퍼링 STT 테스트

```bash
python tests/test_stt_with_audio_file.py \
    --mode buffered \
    --audio /path/to/audio.wav \
    --socketio-url http://localhost:5000
```

**필요한 것:**
- WAV 파일 (16kHz, 16비트, 모노 권장)
- Socket.IO 서버 실행 중

**테스트 과정:**
1. 음성 파일을 읽어서 마이크 스트림처럼 시뮬레이션
2. 버퍼링 STT 실행 (3~5초 수집 후 일괄 처리)
3. 결과를 Socket.IO로 전송
4. 결과 확인

#### 2-2. 스트리밍 STT 테스트

```bash
python tests/test_stt_with_audio_file.py \
    --mode streaming \
    --audio /path/to/audio.wav \
    --socketio-url http://localhost:5000
```

**테스트 과정:**
1. 음성 파일을 읽어서 마이크 스트림처럼 시뮬레이션
2. 스트리밍 STT 실행 (실시간 인식)
3. 중간 결과(`interim`)와 최종 결과(`final`)를 Socket.IO로 전송
4. 결과 확인

#### 음성 파일 준비 방법

**방법 1: ffmpeg 사용 (권장)**

```bash
# 기존 오디오 파일을 16kHz, 16비트, 모노로 변환
ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 output.wav

# 또는 MP4에서 추출
ffmpeg -i input.mp4 -ar 16000 -ac 1 -sample_fmt s16 output.wav
```

**방법 2: Python으로 녹음**

```python
import pyaudio
import wave

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

frames = []
print("녹음 시작...")
for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)

print("녹음 완료")

stream.stop_stream()
stream.close()
p.terminate()

wf = wave.open("output.wav", 'wb')
wf.setnchannels(CHANNELS)
wf.setsampwidth(p.get_sample_size(FORMAT))
wf.setframerate(RATE)
wf.writeframes(b''.join(frames))
wf.close()
```

---

### 3. 실제 마이크를 사용한 통합 테스트

라즈베리파이에 마이크가 연결되어 있다면 실제로 실행해볼 수 있습니다.

```bash
# 라즈베리파이에서 실행
python main.py
```

**테스트 흐름:**
1. 마이크 활성화 및 Wakeword 감지 대기
2. Wakeword 감지 후 버퍼링 STT 실행
3. 결과가 Socket.IO로 전송됨
4. 모바일에서 모드 전환 요청 (`POST /api/stt/mode`)
5. 스트리밍 STT 시작
6. 결과가 Socket.IO로 전송됨

---

## 테스트 시나리오

### 시나리오 1: 버퍼링 STT만 테스트

1. **PC에서 Socket.IO 이벤트 수신 대기**
   ```bash
   python tests/test_socketio_connection.py --socketio-url http://localhost:5000
   ```

2. **라즈베리파이에서 버퍼링 STT 실행 (음성 파일 사용)**
   ```bash
   python tests/test_stt_with_audio_file.py --mode buffered --audio test.wav
   ```

3. **결과 확인**
   - PC 터미널에서 `stt_result` 이벤트 수신 확인
   - 텍스트, 신뢰도 등이 올바르게 전송되는지 확인

### 시나리오 2: 스트리밍 STT만 테스트

1. **PC에서 Socket.IO 이벤트 수신 대기**
   ```bash
   python tests/test_socketio_connection.py --socketio-url http://localhost:5000
   ```

2. **라즈베리파이에서 스트리밍 STT 실행 (음성 파일 사용)**
   ```bash
   python tests/test_stt_with_audio_file.py --mode streaming --audio test.wav
   ```

3. **결과 확인**
   - PC 터미널에서 `stt_result` 이벤트 수신 확인
   - `type=final` 결과가 세션 ID와 함께 전송되는지 확인

### 시나리오 3: 전체 파이프라인 테스트

1. **Socket.IO 서버 실행** (`ai_ar` 프로젝트)
2. **FastAPI 서버 실행** (`ai_server` 프로젝트)
3. **PC에서 Socket.IO 이벤트 수신 대기**
   ```bash
   python tests/test_socketio_connection.py --socketio-url http://localhost:5000
   ```
4. **라즈베리파이에서 STT 실행**
   ```bash
   python main.py
   ```
5. **전체 흐름 확인**
   - `stt_result` → `embedding_result` → `clarify_turn` → `final_answer`

---

## 문제 해결

### 문제: Socket.IO 연결 실패

**원인:**
- Socket.IO 서버가 실행되지 않음
- 포트가 막혀있음
- URL이 잘못됨

**해결:**
```bash
# Socket.IO 서버 실행 확인
netstat -tlnp | grep 5000

# 네트워크 연결 테스트
curl http://localhost:5000
```

### 문제: 음성 파일 읽기 실패

**원인:**
- 파일 형식이 지원되지 않음 (WAV만 지원)
- 샘플레이트/채널 설정이 다름

**해결:**
```bash
# 파일 정보 확인
file audio.wav
ffprobe audio.wav

# 올바른 형식으로 변환
ffmpeg -i input.wav -ar 16000 -ac 1 -sample_fmt s16 output.wav
```

### 문제: GCP STT 인증 오류

**원인:**
- GCP 인증 키 파일이 없거나 경로가 잘못됨
- 환경변수 `GOOGLE_APPLICATION_CREDENTIALS`가 설정되지 않음

**해결:**
```bash
# 환경변수 확인
echo $GOOGLE_APPLICATION_CREDENTIALS

# .env 파일에 설정
echo "GOOGLE_APPLICATION_CREDENTIALS=./secrets/stt-key.json" >> .env
```

---

## 참고사항

- **Postman 사용 불가**: STT는 Socket.IO를 사용하므로 Postman으로 직접 테스트 불가
- **WebSocket vs Socket.IO**: Socket.IO는 WebSocket을 기반으로 하지만 프로토콜이 다름
- **실시간 테스트**: 실제 마이크를 사용하면 가장 정확한 테스트 가능
- **디버깅**: 로그를 자세히 확인하면 문제 파악이 쉬움

---

## 다음 단계

테스트가 성공하면:
1. 실제 라즈베리파이에 배포
2. 마이크 연결 및 Wakeword 감지 테스트
3. 전체 서비스 통합 테스트

