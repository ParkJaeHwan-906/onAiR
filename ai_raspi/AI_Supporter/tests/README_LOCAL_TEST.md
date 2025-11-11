# 로컬 테스트 가이드

전체 시스템을 로컬에서 테스트하는 방법을 정리한 가이드입니다.

## 📋 테스트 전 준비사항

### 1. 환경 변수 설정

#### ai_raspi/AI_Supporter/.env 파일 생성
```env
# GCP STT 인증 키 경로
GOOGLE_APPLICATION_CREDENTIALS=./secrets/stt-key.json

# 언어 설정
LANGUAGE=ko-KR

# Socket.IO 서버 URL (로컬 테스트)
SOCKETIO_SERVER_URL=http://localhost:8000

# STT 설정
STT_BUFFER_DURATION_SEC=4.0
SILENCE_TIMEOUT_SEC=0.5
```

### 2. 필요한 패키지 설치

```bash
# ai_raspi/AI_Supporter
cd ai_raspi/AI_Supporter
pip install -r requirements.txt

# ai_server/rag_server
cd ai_server/rag_server
pip install -r requirements.txt

# ai_ar
cd ai_ar
pip install -r requirements.txt
```

### 3. GCP STT 키 파일 확인
- `ai_raspi/AI_Supporter/secrets/stt-key.json` 파일이 존재하는지 확인

---

## 🚀 테스트 실행 순서

### 1단계: 서버 실행

**터미널 1: FastAPI + Socket.IO 통합 서버 실행**

```bash
cd ai_server/rag_server
uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 --reload
```

**예상 출력:**
```
INFO:     Will watch for changes in these directories: ['...']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [...]
INFO:     Started server process [...]
INFO:     Waiting for application startup.
✅ Socket.IO 통합 활성화됨
INFO:     Application startup complete.
```

**서버가 정상 실행되면:**
- FastAPI: `http://localhost:8000`
- Socket.IO: `http://localhost:8000/ws`

---

### 2단계: 버퍼링 STT 테스트

**터미널 2: 버퍼링 STT 테스트 실행**

```bash
cd ai_raspi/AI_Supporter

# 음성 파일로 테스트 (마이크 없이 가능)
python tests/test_stt_with_audio_file.py \
    --mode buffered \
    --audio tests/stt_buffer.wav \
    --socketio-url http://localhost:8000
```

**예상 출력:**
```
✅ Socket.IO 서버 연결 성공
📄 음성 파일 정보:
   파일: tests/stt_buffer.wav
   샘플레이트: 16000 Hz
🎤 버퍼링 STT 처리 시작...
📤 STT 결과 전송: ...
✅ 버퍼링 STT 테스트 완료!
```

**터미널 1 (서버)에서 확인:**
```
📝 STT 결과 수신 [raspi]: type=final, text=...
📡 Broadcasted 'embedding_result' to 1 clients (['mobile'])
```

---

### 3단계: 전체 버퍼링 STT 플로우 테스트

**터미널 2: 전체 플로우 테스트 (버퍼링 STT → Intent 분류)**

```bash
cd ai_raspi/AI_Supporter

python tests/test_buffered_stt_full_flow.py \
    --audio tests/stt_buffer.wav \
    --socketio-url http://localhost:8000
```

**예상 출력:**
```
✅ Socket.IO 서버 연결 성공
📩 [모바일] 임베딩 결과 수신!
🧠 [모바일] Intent 분류 완료: AI_SUPPORTER
✅ 버퍼링 STT 전체 플로우 테스트 완료!
```

---

### 4단계: Streaming STT 테스트

**터미널 2: Streaming STT 테스트**

```bash
cd ai_raspi/AI_Supporter

python tests/test_stt_with_audio_file.py \
    --mode streaming \
    --audio tests/stt_buffer.wav \
    --socketio-url http://localhost:8000
```

**예상 출력:**
```
✅ Socket.IO 서버 연결 성공
🎤 스트리밍 STT 처리 시작...
📤 Streaming STT 결과 전송: ...
⏱️ 침묵 타임아웃: 0.5초
🕓 침묵 0.5초 경과 → 발화 종료 처리
✅ 스트리밍 STT 테스트 완료!
```

---

### 5단계: 전체 AI_SUPPORTER 플로우 테스트

**터미널 2: 전체 AI_SUPPORTER 플로우 테스트**

```bash
cd ai_raspi/AI_Supporter

python tests/test_ai_supporter_full_flow.py \
    --audio tests/stt_buffer.wav \
    --socketio-url http://localhost:8000 \
    --fastapi-url http://localhost:8000
```

**전체 플로우:**
1. 버퍼링 STT 실행 → STT 결과 전송
2. Intent 분류 → AI_SUPPORTER 분기
3. Streaming STT 시작 → 실시간 음성 인식
4. Clarify 턴 수신 → Clarify 질문 처리
5. Clarify 응답 전송 → FastAPI로 전송
6. 최종 답변 수신 → TTS + 텍스트 수신
7. Streaming STT 종료

**예상 출력:**
```
✅ Socket.IO 서버 연결 성공
📩 [모바일] 임베딩 결과 수신!
🧠 [모바일] Intent 분류 완료: AI_SUPPORTER
🚀 [모바일] AI_SUPPORTER 분기 처리 시작...
🎤 [라즈베리파이] Streaming STT 시작...
📤 [라즈베리파이] Streaming STT 결과 전송: ...
❓ [모바일] Clarify 턴 수신!
✅ [모바일] Clarify 응답 전송 완료
✅ [모바일] 최종 답변 수신!
✅ AI_SUPPORTER 전체 플로우 테스트 완료!
```

---

## 🔍 테스트 시나리오별 체크리스트

### 시나리오 1: 버퍼링 STT
- [ ] Socket.IO 서버 연결 성공
- [ ] 음성 파일 읽기 성공
- [ ] GCP STT 인식 성공
- [ ] STT 결과 Socket.IO로 전송 성공
- [ ] 서버에서 `stt_result` 이벤트 수신 확인

### 시나리오 2: Intent 분류
- [ ] FastAPI에서 Phi-3 임베딩 추출 성공
- [ ] `embedding_result` 이벤트 모바일로 전송 성공
- [ ] 모바일에서 Intent 분류 성공
- [ ] AI_SUPPORTER 분기 처리 성공

### 시나리오 3: Streaming STT
- [ ] Streaming STT 모드 전환 성공
- [ ] 실시간 음성 인식 시작
- [ ] 침묵 타임아웃(0.5초) 감지 성공
- [ ] 발화 종료 처리 성공

### 시나리오 4: Clarify 루프
- [ ] Clarify 턴 수신 성공
- [ ] Clarify 응답 전송 성공
- [ ] FastAPI에서 Clarify 처리 성공
- [ ] 최종 답변 생성 및 전송 성공

---

## ⚠️ 문제 해결

### 1. Socket.IO 연결 실패
```
❌ Socket.IO 서버 연결 실패
```

**해결 방법:**
- 서버가 실행 중인지 확인 (`http://localhost:8000`)
- `SOCKETIO_SERVER_URL` 환경변수 확인
- 방화벽 설정 확인

### 2. GCP STT 인증 오류
```
❌ GCP STT 인증 실패
```

**해결 방법:**
- `GOOGLE_APPLICATION_CREDENTIALS` 경로 확인
- `secrets/stt-key.json` 파일 존재 확인
- GCP 인증 키 파일 유효성 확인

### 3. Phi-3 모델 로딩 실패
```
⚠️ Warning: Phi-3 model loading failed
```

**해결 방법:**
- `transformers` 버전 확인 (4.57.1 권장)
- `torch` 버전 확인
- 모델 다운로드 확인

### 4. 침묵 타임아웃이 너무 짧음
```
🕓 침묵 0.5초 경과 → 발화 종료 처리
```

**해결 방법:**
- `SILENCE_TIMEOUT_SEC` 환경변수로 조정 가능
- 기본값: 0.5초
- 권장 범위: 1.0~2.5초

---

## 📝 테스트 음성 파일 준비

### 기존 파일 사용
- `tests/stt_buffer.wav` (이미 준비됨)

### 새 파일 생성
```bash
# M4A → WAV 변환 (16kHz, 모노, 16-bit)
ffmpeg -i input.m4a -ar 16000 -ac 1 -sample_fmt s16 output.wav
```

---

## 🎯 빠른 테스트 명령어 모음

```bash
# 1. 서버 실행 (터미널 1)
cd ai_server/rag_server
uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 --reload

# 2. 버퍼링 STT 테스트 (터미널 2)
cd ai_raspi/AI_Supporter
python tests/test_stt_with_audio_file.py --mode buffered --audio tests/stt_buffer.wav --socketio-url http://localhost:8000

# 3. 전체 플로우 테스트 (터미널 2)
python tests/test_ai_supporter_full_flow.py --audio tests/stt_buffer.wav --socketio-url http://localhost:8000 --fastapi-url http://localhost:8000
```

---

## ✅ 테스트 완료 확인

모든 테스트가 성공하면:
- ✅ 버퍼링 STT 정상 동작
- ✅ Intent 분류 정상 동작
- ✅ Streaming STT 정상 동작
- ✅ Clarify 루프 정상 동작
- ✅ 전체 플로우 정상 동작

이제 라즈베리파이에 마이크를 연결하여 실제 환경에서 테스트할 준비가 되었습니다! 🎉

