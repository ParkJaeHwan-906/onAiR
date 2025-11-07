# 음성 파일 기반 전체 플로우 테스트 가이드

이 테스트 스크립트는 음성 파일을 사용하여 전체 플로우를 테스트합니다.

## 테스트 시나리오

### 1. AI_SUPPORTER 분기 플로우 테스트

버퍼링 STT → Intent 분류 → CV 모델 실행 → CV 탐지 실패 → Streaming STT → Clarify 루프 → 최종 답변

### 2. OPERATOR 분기 플로우 테스트

버퍼링 STT → Intent 분류 → WebRTC 연결 요청

## 준비 사항

### 1. 음성 파일 준비

- **버퍼링 STT용 음성 파일**: 3~5초 길이의 WAV 파일
  - 예: "AI 도움이 필요해", "통신 연결이 필요해" 등
  - 샘플레이트: 16000 Hz 권장
  - 채널: 모노 (1채널)
  - 포맷: 16비트 PCM WAV

- **Streaming STT용 음성 파일** (AI_SUPPORTER 테스트용)
  - 예: "에어컨이 작동하지 않아요", "온도 조절이 안 돼요" 등
  - 길이: 5~10초 권장

### 2. 서버 실행 확인

- FastAPI 서버 실행 중 (`http://localhost:8000`)
- Socket.IO 서버 실행 중 (`http://localhost:5000`)
- Spring 서버 실행 중 (OPERATOR 테스트용, `https://onair.ai.kr/api`)

### 3. 환경 변수 설정

`.env` 파일에 다음 설정이 필요합니다:

```env
GOOGLE_APPLICATION_CREDENTIALS=./secrets/stt-key.json
GMS_API_KEY=your_gemini_api_key
GCP_TTS_CREDENTIALS_PATH=./credentials/gcp-tts-key.json
```

## 사용 방법

### AI_SUPPORTER 분기 테스트

```bash
python tests/test_audio_file_full_flow.py \
    --buffered-audio tests/stt_buffer.wav \
    --streaming-audio tests/stt_stream.wav \
    --socketio-url http://localhost:5000 \
    --fastapi-url http://localhost:8000 \
    --test-type ai_supporter
```

**예상 플로우:**
1. 버퍼링 STT 처리 (음성 파일 → STT → 텍스트)
2. Intent 분류 (Gemini-Flash)
3. `intent_result` 이벤트 수신 (AI_SUPPORTER)
4. CV 모델 실행 (보류 상태, 항상 탐지 실패)
5. `cv_detection_failed` 이벤트 수신 (모바일 + 라즈베리파이)
6. Streaming STT 세션 시작 (음성 파일 사용)
7. Streaming STT 결과 전송
8. Clarify 질문/답변 턴 수신 (`clarify_qa_turn`)
9. 최종 답변 수신 (`final_answer`)

### OPERATOR 분기 테스트

```bash
python tests/test_audio_file_full_flow.py \
    --buffered-audio tests/stt_buffer.wav \
    --socketio-url http://localhost:5000 \
    --fastapi-url http://localhost:8000 \
    --spring-url https://onair.ai.kr/api \
    --access-token eyJhbGciOiJIUzI1NiJ9... \
    --test-type operator
```

**예상 플로우:**
1. 버퍼링 STT 처리 (음성 파일 → STT → 텍스트)
2. Intent 분류 (Gemini-Flash)
3. `intent_result` 이벤트 수신 (OPERATOR)
4. WebRTC 연결 요청 (`/webrtc/request`)

## 테스트 결과 확인

### AI_SUPPORTER 테스트 성공 조건

- ✅ Intent 결과 수신 (`intent_result`)
- ✅ CV 탐지 실패 이벤트 수신 (`cv_detection_failed`)
- ✅ Clarify 질문/답변 턴 수신 (`clarify_qa_turn`) 또는 최종 답변 수신 (`final_answer`)

### OPERATOR 테스트 성공 조건

- ✅ Intent 결과 수신 (`intent_result`, Intent: OPERATOR)
- ✅ WebRTC 연결 요청 성공 (HTTP 200/202)

## 문제 해결

### Intent 결과가 수신되지 않는 경우

1. FastAPI 서버가 실행 중인지 확인
2. Socket.IO 서버가 실행 중인지 확인
3. 네트워크 연결 확인
4. 로그에서 에러 메시지 확인

### CV 탐지 실패 이벤트가 수신되지 않는 경우

- CV 모델이 보류 상태이므로 항상 탐지 실패로 처리됩니다
- Intent가 AI_SUPPORTER인지 확인

### Streaming STT가 동작하지 않는 경우

1. 음성 파일 경로 확인
2. GCP STT 인증 정보 확인 (`GOOGLE_APPLICATION_CREDENTIALS`)
3. 음성 파일 포맷 확인 (16kHz, 모노, 16비트 PCM)

### WebRTC 연결 요청이 실패하는 경우

1. Spring 서버 URL 확인
2. 액세스 토큰 유효성 확인
3. 네트워크 연결 확인
4. Spring 서버 로그 확인

## 참고 사항

- CV 모델은 현재 보류 상태이므로 항상 탐지 실패로 처리됩니다
- 실제 CV 모델 통합 후에는 오류 탐지 성공 케이스도 테스트 가능합니다
- LiveKit 연결은 WebRTC 연결 요청까지만 테스트하며, 실제 WebRTC 세션 연결은 별도로 테스트해야 합니다

