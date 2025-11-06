# AI_SUPPORTER 전체 플로우 테스트 가이드

## ✅ 테스트 환경 체크리스트

### 1. 필수 서버 실행

#### 방법 1: 통합 서버 실행 (권장)
FastAPI 서버가 Socket.IO도 포함하므로 하나만 실행하면 됩니다.

```bash
# 터미널 1: FastAPI + Socket.IO 통합 서버 실행
cd ai_server/rag_server
uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 --reload
```

**예상 출력:**
```
✅ Socket.IO 통합 활성화됨
INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### 방법 2: 별도 서버 실행 (선택사항)
Socket.IO 서버와 FastAPI 서버를 별도로 실행할 수도 있습니다.

```bash
# 터미널 1: Socket.IO 서버 (포트 5000)
cd ai_ar
uvicorn app.main:asgi_app --host 0.0.0.0 --port 5000 --reload

# 터미널 2: FastAPI 서버 (포트 8000)
cd ai_server/rag_server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 필수 파일 확인

- [ ] 음성 파일: `ai_raspi/AI_Supporter/tests/stt_buffer.wav`
- [ ] GCP STT 키: `ai_raspi/AI_Supporter/secrets/stt-key.json`
- [ ] GCP TTS 키: `ai_server/rag_server/credentials/tts-key.json`
- [ ] RAG 데이터: `ai_server/rag_server/app/data/samkos_cleaned.jsonl`
- [ ] FAISS 인덱스: `ai_server/rag_server/app/data/faiss_index/samkos.index`

### 3. 환경변수 설정 (선택사항)

`.env` 파일이 있다면 확인:
```bash
# ai_raspi/AI_Supporter/.env
SOCKETIO_SERVER_URL=http://localhost:8000
GOOGLE_APPLICATION_CREDENTIALS=./secrets/stt-key.json
LANGUAGE=ko-KR
SILENCE_TIMEOUT_SEC=2.5  # 새로 추가된 침묵 타임아웃

# ai_server/rag_server/.env (필요시)
GOOGLE_APPLICATION_CREDENTIALS=./credentials/tts-key.json
```

### 4. 테스트 실행

#### 전체 플로우 테스트

```bash
# 터미널 2: 테스트 실행
cd ai_raspi/AI_Supporter
python tests/test_ai_supporter_full_flow.py \
    --audio tests/stt_buffer.wav \
    --socketio-url http://localhost:8000 \
    --fastapi-url http://localhost:8000
```

## 📋 테스트 플로우 확인 사항

### ✅ 단계별 확인 포인트

| 단계 | 확인 사항 | 예상 출력 |
|------|----------|----------|
| 1. 버퍼링 STT | 음성 파일 → STT 결과 | `📝 STT 결과: ...` |
| 2. Intent 분류 | 임베딩 수신 → AI_SUPPORTER 분기 | `✅ Intent 분류: AI_SUPPORTER` |
| 3. Streaming STT 시작 | 라즈베리파이 Streaming STT 모드 전환 | `🔗 Streaming STT 세션 시작` |
| 4. Streaming STT 실행 | 음성 파일 → Streaming STT 결과 | `🔄 STT 중간 결과: ...` |
| 5. Clarify 턴 수신 | FastAPI → Clarify 판정 → 질문 전송 | `❓ Clarify 턴 수신!` |
| 6. Clarify 응답 | 모바일 → FastAPI로 응답 전송 | `✅ Clarify 응답 전송 완료` |
| 7. 최종 답변 수신 | GPT-4o + RAG → TTS → 모바일 전송 | `✅ 최종 답변 수신!` |
| 8. Streaming STT 종료 | 라즈베리파이 Streaming STT 세션 종료 | `🛑 Streaming STT 종료 신호` |

## 🔧 문제 해결

### 문제 1: Socket.IO 연결 실패
```bash
# 포트 확인
netstat -ano | findstr ":8000"
# 또는
lsof -i :8000  # macOS/Linux
```

### 문제 2: 모듈 import 오류
```bash
# Python 경로 확인
cd ai_raspi/AI_Supporter
python -c "import sys; print('\n'.join(sys.path))"
```

### 문제 3: GCP 인증 오류
```bash
# 환경변수 확인
echo $GOOGLE_APPLICATION_CREDENTIALS  # Linux/Mac
echo %GOOGLE_APPLICATION_CREDENTIALS%  # Windows
```

### 문제 4: 임베딩 결과 수신 타임아웃
- FastAPI 서버가 정상 실행 중인지 확인
- Socket.IO 이벤트 핸들러가 등록되었는지 확인
- 네트워크 연결 확인

## 📝 테스트 예상 출력

```
✅ 모바일 클라이언트: Socket.IO 서버 연결 성공
✅ 라즈베리파이 클라이언트: Socket.IO 서버 연결 성공
🎤 버퍼링 STT 처리 시작...
📩 [모바일] 임베딩 결과 수신!
🧠 [모바일] Intent 분류 완료: AI_SUPPORTER
🚀 [모바일] AI_SUPPORTER 분기 처리 시작...
🎤 [라즈베리파이] Streaming STT 시작...
⏱️ 침묵 타임아웃: 2.5초
🔄 STT 중간 결과: 문제 상황을...
🕓 침묵 2.5초 경과 → 발화 종료 처리
📝 STT 최종 결과: 문제 상황을...
❓ [모바일] Clarify 턴 수신!
✅ Clarify 응답 전송 완료
✅ [모바일] 최종 답변 수신!
✅ AI_SUPPORTER 전체 플로우 테스트 완료!
```

## 🚀 빠른 시작

```bash
# 1. 서버 실행 (터미널 1)
cd ai_server/rag_server
uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 --reload

# 2. 테스트 실행 (터미널 2)
cd ai_raspi/AI_Supporter
python tests/test_ai_supporter_full_flow.py \
    --audio tests/stt_buffer.wav \
    --socketio-url http://localhost:8000 \
    --fastapi-url http://localhost:8000
```

준비 완료! 🎉

