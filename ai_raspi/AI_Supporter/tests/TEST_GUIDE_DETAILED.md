# AI_SUPPORTER 전체 플로우 테스트 상세 가이드

## 🎯 목표
버퍼링 STT → Intent 분류 → AI_SUPPORTER 분기 → Streaming STT → Clarify → 최종 답변의 전체 플로우를 테스트합니다.

---

## 📋 0단계: 사전 준비

### 0-1. 필수 파일 확인

Windows PowerShell에서 실행:

```powershell
# 작업 디렉토리 이동
cd C:\Users\SSAFY\Documents\S13P31A407

# 음성 파일 확인
Test-Path ai_raspi\AI_Supporter\tests\stt_buffer.wav
# 출력: True여야 함

# GCP STT 키 확인
Test-Path ai_raspi\AI_Supporter\secrets\stt-key.json
# 출력: True여야 함

# GCP TTS 키 확인
Test-Path ai_server\rag_server\credentials\tts-key.json
# 출력: True여야 함

# RAG 데이터 확인
Test-Path ai_server\rag_server\app\data\samkos_cleaned.jsonl
# 출력: True여야 함

# FAISS 인덱스 확인
Test-Path ai_server\rag_server\app\data\faiss_index\samkos.index
# 출력: True여야 함
```

**파일이 없으면:**
- 음성 파일: `tests/stt_buffer.m4a`를 WAV로 변환
- GCP 키: 프로젝트에서 제공받아야 함
- RAG 데이터/FAISS: 프로젝트에서 제공받아야 함

### 0-2. Redis 서버 확인 (필수)

```powershell
# Redis가 실행 중인지 확인
# Windows에서는 Redis가 설치되어 있어야 함
# 또는 Docker로 실행:
docker run -d --name redis -p 6379:6379 redis
```

### 0-3. Python 패키지 확인

```powershell
# ai_raspi 패키지 확인
cd ai_raspi\AI_Supporter
python -c "import socketio; print('✅ socketio 설치됨')"

# ai_server 패키지 확인
cd ..\..\ai_server\rag_server
python -c "import fastapi; print('✅ fastapi 설치됨')"
```

---

## 🚀 1단계: FastAPI + Socket.IO 서버 실행

### 터미널 1을 열고 실행:

```powershell
# 작업 디렉토리로 이동
cd C:\Users\SSAFY\Documents\S13P31A407\ai_server\rag_server

# FastAPI + Socket.IO 통합 서버 실행
uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 --reload
```

**예상 출력:**
```
✅ Socket.IO 통합 활성화됨
INFO:     Will watch for changes...
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

**중요:** 이 터미널은 계속 켜두세요. 서버가 실행 중이어야 테스트가 가능합니다.

**오류 발생 시:**
- `ModuleNotFoundError`: `pip install -r requirements.txt` 실행
- `Port 8000 already in use`: 다른 프로세스가 사용 중이면 종료 또는 다른 포트 사용
- `Redis connection failed`: Redis 서버 실행 확인

---

## 🧪 2단계: 테스트 실행

### 터미널 2를 새로 열고 실행:

```powershell
# 작업 디렉토리로 이동
cd C:\Users\SSAFY\Documents\S13P31A407\ai_raspi\AI_Supporter

# 테스트 실행
python tests/test_ai_supporter_full_flow.py --audio tests/stt_buffer.wav --socketio-url http://localhost:8000 --fastapi-url http://localhost:8000
```

**PowerShell에서 긴 명령어를 여러 줄로 나누려면:**

```powershell
python tests/test_ai_supporter_full_flow.py `
    --audio tests/stt_buffer.wav `
    --socketio-url http://localhost:8000 `
    --fastapi-url http://localhost:8000
```

---

## 📊 3단계: 예상 출력 확인

### 터미널 2 (테스트 스크립트) 출력:

```
📱 [1단계] 모바일 클라이언트 연결 중...
✅ 모바일 클라이언트: Socket.IO 서버 연결 성공
📱 모바일 디바이스 등록 완료

🔌 [2단계] 라즈베리파이 클라이언트 연결 중...
✅ 라즈베리파이 클라이언트: Socket.IO 서버 연결 성공
🔗 라즈베리파이 디바이스 등록 완료

🎤 [3단계] 버퍼링 STT 실행 중...
📄 음성 파일 정보:
   파일: tests/stt_buffer.wav
   샘플레이트: 16000 Hz
   채널: 1
🎤 버퍼링 STT 처리 시작...
📝 STT 결과: [인식된 텍스트]
📤 STT 결과 전송: type=final, text=...

⏳ [4단계] 임베딩 결과 수신 대기 중...
✅ 임베딩 결과 수신 완료! (X초 소요)

📩 [모바일] 임베딩 결과 수신!
   텍스트: [인식된 텍스트]
   차원: 3072
🧠 [모바일] Intent 분류 완료: AI_SUPPORTER (신뢰도: 0.85)
🚀 [모바일] AI_SUPPORTER 분기 처리 시작...
   → TTS: 'AI Supporter가 도와드리겠습니다.' 재생 (시뮬레이션)
   → UI: 'AI Supporter ON' 표시 (시뮬레이션)
   → 세션 ID 생성: [UUID]

🎤 [5단계] 라즈베리파이 Streaming STT 시작...
   → 세션 ID: [UUID]
   → 마이크 ON (Streaming STT 모드)

📤 [6단계] Streaming STT 실행 중...
🔗 Streaming STT 세션 시작: session_id=[UUID]
⏱️ 침묵 타임아웃: 2.5초
🔄 STT 중간 결과: [인식된 텍스트]
🕓 침묵 2.5초 경과 (타임아웃: 2.5초) → 발화 종료 처리
📝 STT 최종 결과: [인식된 텍스트]

⏳ [7단계] Clarify 턴 수신 대기 중...
✅ Clarify 턴 수신 완료! (X초 소요)

❓ [모바일] Clarify 턴 수신!
   세션 ID: [UUID]
   턴 ID: 1
   상태: RED 또는 YELLOW
   질문: [Clarify 질문]

✅ Clarify 응답 전송 완료: session_id=[UUID], turn_id=1, text=...

⏳ [8단계] 최종 답변 수신 대기 중...
✅ 최종 답변 수신 완료! (X초 소요)

✅ [모바일] 최종 답변 수신!
   세션 ID: [UUID]
   답변: [GPT-4o가 생성한 답변]
   오디오 URL: [또는 오디오 콘텐츠]

🧹 [9단계] 연결 정리 중...
✅ AI_SUPPORTER 전체 플로우 테스트 완료!
```

### 터미널 1 (FastAPI 서버) 출력:

```
📝 STT 결과 수신 [raspi]: type=final, text=[인식된 텍스트]
📦 Phi-3 모델 로드 중...
✅ Phi-3 임베딩 추출 완료
📡 Broadcasted 'embedding_result' to 1 clients (['mobile'])

📝 STT 결과 수신 [raspi]: type=final, text=[인식된 텍스트], session_id=[UUID]
✅ Clarify 처리 시작: session_id=[UUID]
🔍 Hybrid 검색 실행...
✅ Clarify 판정: RED (또는 YELLOW, GREEN)
📡 Broadcasted 'clarify_turn' to 1 clients (['mobile'])

📝 Clarify 응답 수신: session_id=[UUID], turn_id=1, response=...
✅ Clarify 처리 완료
📡 Broadcasted 'final_answer' to 1 clients (['mobile'])
```

---

## ⚠️ 4단계: 문제 해결

### 문제 1: Socket.IO 연결 실패

**증상:**
```
❌ 모바일 클라이언트 연결 실패: Connection refused by the server
```

**해결:**
```powershell
# 포트 8000이 사용 중인지 확인
netstat -ano | findstr ":8000"

# FastAPI 서버가 실행 중인지 확인 (터미널 1 확인)
# 서버가 실행되지 않았다면 시작
```

### 문제 2: 임베딩 결과 수신 타임아웃

**증상:**
```
❌ 임베딩 결과 수신 타임아웃 (30초 초과)
```

**해결:**
1. FastAPI 서버가 정상 실행 중인지 확인
2. Phi-3 모델 로드 확인 (서버 로그 확인)
3. Socket.IO 이벤트 핸들러 등록 확인

### 문제 3: GCP STT 오류

**증상:**
```
❌ google.cloud.speech 오류
```

**해결:**
```powershell
# GCP 인증 키 확인
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\Users\SSAFY\Documents\S13P31A407\ai_raspi\AI_Supporter\secrets\stt-key.json"

# 또는 .env 파일에 설정
# GOOGLE_APPLICATION_CREDENTIALS=./secrets/stt-key.json
```

### 문제 4: Clarify 턴 수신 타임아웃

**증상:**
```
⚠️ Clarify 턴 수신 타임아웃 (계속 진행)
```

**해결:**
1. Redis 서버 실행 확인
2. FastAPI 서버 로그에서 Clarify 처리 확인
3. Socket.IO 브로드캐스트 확인

### 문제 5: 모듈 import 오류

**증상:**
```
ModuleNotFoundError: No module named 'xxx'
```

**해결:**
```powershell
# ai_raspi 패키지 설치
cd ai_raspi\AI_Supporter
pip install -r requirements.txt

# ai_server 패키지 설치
cd ..\..\ai_server\rag_server
pip install -r requirements.txt
```

---

## ✅ 5단계: 성공 확인

### 완료 조건:

- [ ] 버퍼링 STT 결과가 Socket.IO로 전송됨
- [ ] 모바일 클라이언트가 임베딩을 수신함
- [ ] Intent가 AI_SUPPORTER로 분류됨
- [ ] Streaming STT 세션이 시작됨
- [ ] Clarify 턴이 수신됨
- [ ] Clarify 응답이 전송됨
- [ ] 최종 답변이 수신됨
- [ ] 테스트가 성공적으로 완료됨

---

## 🔄 6단계: 재실행 (필요시)

테스트를 다시 실행하려면:

1. **터미널 1 (서버)**: `CTRL+C`로 종료 후 다시 시작
2. **터미널 2 (테스트)**: 명령어만 다시 실행

**빠른 재실행:**
```powershell
# 터미널 2에서 위로 스크롤해서 명령어 다시 실행
```

---

## 📝 추가 팁

### 테스트 로그 저장

```powershell
# 테스트 출력을 파일로 저장
python tests/test_ai_supporter_full_flow.py `
    --audio tests/stt_buffer.wav `
    --socketio-url http://localhost:8000 `
    --fastapi-url http://localhost:8000 | Tee-Object -FilePath test_output.log
```

### 침묵 타임아웃 조정

```powershell
# 침묵 타임아웃을 3초로 설정하고 테스트
$env:SILENCE_TIMEOUT_SEC="3.0"
python tests/test_ai_supporter_full_flow.py ...
```

### 버퍼링 시간 조정

```powershell
# 버퍼링 시간을 5초로 설정
python tests/test_ai_supporter_full_flow.py `
    --audio tests/stt_buffer.wav `
    --buffer-duration 5.0 `
    --socketio-url http://localhost:8000 `
    --fastapi-url http://localhost:8000
```

---

## 🎉 완료!

모든 단계가 성공하면 전체 플로우가 정상 동작하는 것입니다!

**다음 단계:**
- 실제 마이크로 테스트
- 다른 음성 파일로 테스트
- 다양한 Intent로 테스트

