# 경량 모델 변경 후 전체 플로우 테스트 가이드

경량 모델로 변경한 후 전체 플로우가 정상 동작하는지 테스트하는 가이드입니다.

## 📋 테스트 전 확인사항

### 1. FastAPI 서버 설정 확인

**`.env` 파일 또는 환경변수:**
```env
USE_LIGHTWEIGHT_EMBEDDING=True
LIGHTWEIGHT_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
PHI3_EMBEDDING_DIM=3072
```

### 2. 서버 로그에서 경량 모델 로드 확인

서버 시작 시 다음 메시지가 표시되어야 합니다:
```
📦 Loading lightweight embedding model for intent classification: BAAI/bge-small-en-v1.5
✓ Lightweight embedding model loaded: BAAI/bge-small-en-v1.5
✓ Model dimension: 384 → will be transformed to 3072
```

---

## 🚀 테스트 실행 순서

### 1단계: FastAPI 서버 실행

**터미널 1: FastAPI + Socket.IO 통합 서버 실행**

```bash
cd ai_server/rag_server
uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 --reload
```

**확인 사항:**
- ✅ 경량 모델 로드 메시지 확인
- ✅ "Application startup complete" 메시지 확인
- ✅ Socket.IO 통합 활성화 확인

---

### 2단계: 전체 플로우 테스트 실행

**터미널 2: 버퍼링 STT → 경량 모델 임베딩 → Intent 분류 테스트**

```bash
cd ai_raspi/AI_Supporter

python tests/test_buffered_stt_full_flow.py \
    --audio tests/stt_buffer.wav \
    --socketio-url http://localhost:8000
```

---

## ✅ 예상 결과

### 터미널 1 (서버) 출력:

```
INFO:     Application startup complete.
📦 Loading lightweight embedding model for intent classification: BAAI/bge-small-en-v1.5
✓ Lightweight embedding model loaded: BAAI/bge-small-en-v1.5
✓ Model dimension: 384 → will be transformed to 3072

📝 STT 결과 수신 [raspi]: type=final, text=AI 서포터 도움이 필요해
✅ STT 텍스트 처리 완료: 'AI 서포터 도움이 필요해' → 모바일로 임베딩 전송
📡 Broadcasted 'embedding_result' to 1 clients (['mobile'])
```

### 터미널 2 (테스트 스크립트) 출력:

```
✅ Socket.IO 서버 연결 성공
📄 [3단계] 음성 파일 읽기 중...
🎤 [4단계] 버퍼링 STT 실행 중...
📤 [라즈베리파이] STT 결과 전송:
   타입: final
   텍스트: AI 서포터 도움이 필요해
   신뢰도: 0.95

⏳ [5단계] 임베딩 결과 수신 대기 중...
📩 [모바일] 임베딩 결과 수신!
   텍스트: AI 서포터 도움이 필요해
   차원: 3072
   신뢰도: 0.95

🧠 [모바일] Intent 분류 시뮬레이션:
   임베딩 차원: 3072 ✅
   Intent 분류 결과: AI_SUPPORTER (신뢰도: 0.85)
   분기 처리: AI_SUPPORTER 분기 처리 시작...

✅ 버퍼링 STT 전체 플로우 테스트 완료!
```

---

## 🔍 체크리스트

### 서버 측 확인:
- [ ] 경량 모델 로드 성공
- [ ] STT 결과 수신 성공
- [ ] 임베딩 추출 성공 (384차원 → 3072차원 변환)
- [ ] 모바일로 `embedding_result` 전송 성공

### 클라이언트 측 확인:
- [ ] Socket.IO 연결 성공
- [ ] STT 결과 전송 성공
- [ ] 임베딩 결과 수신 성공
- [ ] 임베딩 차원 3072 확인
- [ ] Intent 분류 시뮬레이션 성공

---

## ⚠️ 문제 해결

### 1. 경량 모델 로드 실패

**증상:**
```
⚠️ Warning: Lightweight embedding model loading failed
```

**해결 방법:**
```bash
# sentence-transformers 재설치
pip install --upgrade sentence-transformers

# 모델 수동 다운로드
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
```

### 2. 임베딩 차원 불일치

**증상:**
```
❌ 임베딩 차원 불일치: 예상 3072, 실제 384
```

**해결 방법:**
- `model_loader.py`의 차원 변환 로직 확인
- 패딩 추가 로직이 정상 동작하는지 확인

### 3. Intent 분류 실패

**증상:**
```
❌ Intent 분류 실패
```

**해결 방법:**
- 모바일 ONNX 모델이 3072차원 입력을 받는지 확인
- 임베딩 값이 정상 범위인지 확인 (NaN, Inf 체크)

---

## 📊 성능 비교 (참고)

### 경량 모델 vs Phi-3 (예상)

| 항목 | 경량 모델 | Phi-3 |
|------|----------|-------|
| 메모리 사용 | ~100MB | ~7GB |
| 추론 속도 | 빠름 | 느림 |
| 임베딩 품질 | 보통 | 높음 |
| Intent 분류 정확도 | 테스트 필요 | 높음 (예상) |

**테스트 후 Intent 분류 정확도를 확인하고, 필요 시 조정하세요.**

---

## 🎯 다음 단계

1. **테스트 실행**: 위 순서대로 테스트 진행
2. **결과 확인**: Intent 분류 정확도 확인
3. **성능 평가**: 경량 모델 성능이 충분한지 판단
4. **필요 시 조정**: 성능이 부족하면 다른 경량 모델 시도 또는 ONNX 전환 검토

---

## 📝 테스트 명령어 요약

```bash
# 1. 서버 실행 (터미널 1)
cd ai_server/rag_server
uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 --reload

# 2. 테스트 실행 (터미널 2)
cd ai_raspi/AI_Supporter
python tests/test_buffered_stt_full_flow.py --audio tests/stt_buffer.wav --socketio-url http://localhost:8000
```

테스트 결과를 확인하고 문제가 있으면 알려주세요!

