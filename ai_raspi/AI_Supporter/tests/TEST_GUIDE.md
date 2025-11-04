# 🧪 테스트 가이드

설계된 시스템을 단계별로 테스트하는 방법입니다.

> **🍓 라즈베리파이에서 테스트하려면:** `TEST_GUIDE_RASPBERRYPI.md`를 참고하세요.

## 📋 사전 준비

1. **환경 변수 설정** (`.env` 파일 생성 - 프로젝트 루트에)
```env
# 앱 서버 설정
APP_SERVER_URL=http://localhost:8080
WEBHOOK_ENDPOINT=/api/stt/start

# STT 버퍼링 시간 (초)
STT_BUFFER_DURATION_SEC=4.0

# GCP 인증 (필요시)
GOOGLE_APPLICATION_CREDENTIALS=./secrets/stt-key.json
LANGUAGE=ko-KR
```

2. **의존성 설치**
```bash
pip install -r requirements.txt
```

## 🧪 테스트 방법

### 1. 개별 모듈 테스트

각 모듈을 독립적으로 테스트할 수 있습니다:

```bash
python tests/test_modules.py
```

**테스트 항목:**
- ✅ 마이크 스트림 (pause/resume)
- ✅ Wakeword 감지기
- ✅ Webhook 전송
- ✅ STT 버퍼링 (GCP 호출)

### 2. Webhook 테스트 서버

앱 서버 대신 webhook 요청을 받아 확인:

**터미널 1:**
```bash
python tests/test_webhook_server.py
```

**터미널 2:**
```bash
python tests/test_modules.py
# 메뉴에서 3번 선택 (Webhook 전송 테스트)
```

예상 출력:
```
✅ Webhook 수신: {'type': 'stt_start', 'message': 'STT 세션이 시작되었습니다.'}
```

### 3. WebSocket 클라이언트 테스트

STT 결과를 실시간으로 확인:

**터미널 1:**
```bash
python main.py
```

**터미널 2:**
```bash
python tests/test_websocket_client.py
```

**터미널 1에서 wakeword 감지 후:**
- WebSocket 클라이언트가 실시간으로 메시지를 수신합니다
- `stt_start` → 음성 수집 → STT 결과 → `stt_end` 순서로 확인

### 4. 통합 테스트 (전체 시스템)

**터미널 1: Webhook 테스트 서버**
```bash
python tests/test_webhook_server.py
```

**터미널 2: WebSocket 클라이언트**
```bash
python tests/test_websocket_client.py
```

**터미널 3: 메인 서버**
```bash
python main.py
```

**테스트 시나리오:**
1. ✅ 서버 시작 확인
   - `🎧 STT 루프 대기 시작 (마이크 OFF)`
   - `🎧 Wakeword 감지 대기 중... (onAir)`

2. ✅ Wakeword 감지
   - "onAir"라고 말하기
   - `🚀 Wakeword 감지됨!` 확인

3. ✅ Webhook 전송 확인
   - 터미널 1에서 `✅ Webhook 수신` 확인

4. ✅ 마이크 활성화 확인
   - `🔊 마이크 ON (활성 상태)` 확인

5. ✅ 음성 수집 확인
   - `🎤 음성 수집 시작 (4.0초)...` 확인
   - 3~5초 동안 말하기

6. ✅ STT 결과 확인
   - 터미널 2에서 WebSocket으로 결과 수신 확인
   - `📝 [final] {인식된 텍스트}` 확인

7. ✅ 마이크 종료 확인
   - `🔇 마이크 OFF (대기 상태)` 확인
   - `🟢 STT 세션 종료, 다시 대기 중...` 확인

## 🔍 각 단계별 확인 포인트

### ① 대기 상태
- [ ] 마이크가 OFF 상태인지 확인
- [ ] Wakeword 감지기가 실행 중인지 확인
- [ ] 콘솔에 대기 메시지 출력

### ② Wakeword 감지
- [ ] "onAir" 말했을 때 감지되는지 확인
- [ ] 신뢰도가 0.75 이상인지 확인
- [ ] 콘솔에 감지 메시지 출력

### ③ Webhook 전송
- [ ] HTTP POST 요청이 전송되는지 확인
- [ ] Webhook 서버에서 요청 수신 확인
- [ ] 실패 시에도 계속 진행되는지 확인

### ④ 마이크 활성화
- [ ] 마이크가 ON 상태로 전환되는지 확인
- [ ] 콘솔에 "마이크 ON" 메시지 출력

### ⑤ 음성 수집
- [ ] 3~5초 동안 음성 수집되는지 확인
- [ ] 진행 상황이 표시되는지 확인
- [ ] 버퍼에 데이터가 쌓이는지 확인

### ⑥ STT 요청
- [ ] GCP에 요청이 전송되는지 확인
- [ ] 콘솔에 "GCP STT 요청 전송 중" 메시지 출력

### ⑦ STT 결과 수신
- [ ] GCP에서 결과가 반환되는지 확인
- [ ] 인식된 텍스트와 신뢰도 확인

### ⑧ WebSocket 전송
- [ ] WebSocket 클라이언트에서 결과 수신 확인
- [ ] JSON 형식이 올바른지 확인

### ⑨ 마이크 종료
- [ ] 마이크가 OFF 상태로 전환되는지 확인
- [ ] 다시 대기 상태로 복귀하는지 확인

## 🐛 문제 해결

### 마이크가 작동하지 않음
- 마이크 권한 확인
- `DEVICE_INDEX` 환경 변수 설정 확인
- PyAudio 설치 확인

### Wakeword가 감지되지 않음
- 모델 파일 경로 확인 (`Wakeword/wakeword_onair_cnn.tflite`)
- 신뢰도 임계값 조정 (기본 0.75)
- 마이크 입력 레벨 확인

### Webhook 전송 실패
- Webhook 서버가 실행 중인지 확인
- `APP_SERVER_URL` 설정 확인
- 네트워크 연결 확인

### STT 결과가 없음
- GCP 인증 키 확인 (`secrets/stt-key.json`)
- 음성 입력 레벨 확인
- GCP API 할당량 확인

### WebSocket 연결 실패
- 메인 서버가 실행 중인지 확인
- 포트 8000이 사용 가능한지 확인

## 📊 예상 출력 예시

```
🎧 STT 루프 대기 시작 (마이크 OFF)
✅ Wakeword 모델 로드 완료: .../wakeword_onair_cnn.tflite
🎧 Wakeword 감지 대기 중... (onAir)
🚀 Wakeword 감지됨! (신뢰도: 87.5%)
🚀 Wakeword 감지됨: STT 세션 시작
✅ Webhook 전송 성공: http://localhost:8080/api/stt/start
🔊 마이크 ON (활성 상태)
🎤 음성 수집 시작 (4.0초)...
   수집 중... 1.0초 / 4.0초
   수집 중... 2.0초 / 4.0초
   수집 중... 3.0초 / 4.0초
   수집 중... 4.0초 / 4.0초
✅ 음성 수집 완료 (128000 bytes)
📤 GCP STT 요청 전송 중...
📝 STT 결과: 안녕하세요 (신뢰도: 0.95)
🔇 마이크 OFF (대기 상태)
🟢 STT 세션 종료, 다시 대기 중... (마이크 OFF)
```

## ✅ 체크리스트

전체 시스템 테스트 완료 체크리스트:

- [ ] 개별 모듈 테스트 통과
- [ ] Webhook 전송 성공
- [ ] WebSocket 연결 및 메시지 수신 확인
- [ ] Wakeword 감지 정상 동작
- [ ] 마이크 상태 관리 (ON/OFF) 정상
- [ ] STT 결과 정확도 확인
- [ ] 전체 흐름 정상 동작
- [ ] 에러 처리 확인

