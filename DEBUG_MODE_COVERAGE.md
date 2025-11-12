# 🐛 디버그 모드 적용 현황

## 📋 개요

각 단계별로 Enter를 눌러야 다음 단계로 넘어가는 디버그 모드(`wait_for_next_step`) 적용 현황을 정리합니다.

## ⚙️ 디버그 모드 설정

### FastAPI 서버
```python
# app/core/config.py
DEBUG_STEP_BY_STEP: bool = False  # True로 설정 시 활성화
DEBUG_STEP_TRIGGER_FILE: str = "/tmp/next_step"  # 파일 트리거 방식
DEBUG_STEP_WAIT_TIMEOUT: int = 300  # 최대 대기 시간 (5분)
```

**사용법:**
- `DEBUG_STEP_BY_STEP=True`로 설정
- 각 단계 완료 후 `/tmp/next_step` 파일 생성 대기
- `touch /tmp/next_step` 또는 `echo 'auto' > /tmp/next_step` (자동 모드)

### 라즈베리파이 Python 3.10
```python
# config/settings.py
DEBUG_STEP_BY_STEP: bool = False  # True로 설정 시 활성화
```

**사용법:**
- `DEBUG_STEP_BY_STEP=True`로 설정
- 각 단계 완료 후 Enter 키 입력 대기
- `auto` 입력 시 이후 단계 자동 진행

---

## ✅ 적용된 단계 (FastAPI 서버)

### 1. Wakeword 감지 플로우
- ✅ [단계 2-1] Wakeword 감지 이벤트 수신 완료
- ✅ [단계 2-1-1] 모바일로 Wakeword 감지 이벤트 전송 완료
- ✅ [단계 2-2] 모바일 음성 파일 재생 완료 이벤트 수신 완료
- ✅ [단계 2-2-1] 라즈베리파이로 음성 파일 재생 완료 이벤트 전송 완료

### 2. Intent 분류 플로우
- ✅ [단계 6] STT 결과 수신 완료
- ✅ [단계 6-1] SSE 연결 시작 요청 전송 완료
- ✅ [단계 7] Intent 분류 완료
- ✅ [단계 8] 모바일로 intent_result 이벤트 전송 완료
- ✅ [단계 8-1] 모바일 Intent 음성 파일 재생 완료 이벤트 수신 완료

### 3. CV 로직 실행
- ✅ [단계 9] CV 모델 실행 완료
- ✅ [단계 9] CV 모델 실행 완료 (탐지 실패)
- ✅ [단계 9] CV 모델 오류 탐지 성공

### 4. CV 탐지 실패 플로우
- ✅ [단계 10] 모바일로 cv_detection_failed 이벤트 전송 완료
- ✅ [단계 11] 라즈베리파이로 cv_detection_failed 이벤트 전송 완료
- ✅ [단계 12-1] 모바일 오디오 재생 완료 이벤트 수신 완료
- ✅ [단계 12-2] 라즈베리파이로 Streaming STT 시작 신호 전송 완료

### 5. CV 탐지 성공 → RAG 기반 답변 생성
- ✅ [단계 10] RAG 쿼리 생성 완료
- ✅ [단계 11] RAG 검색 완료
- ✅ [단계 12] 최종 답변 생성 완료 (GPT-4o)
- ✅ [단계 13] 최종 답변 TTS 변환 완료
- ✅ [단계 14] 모바일로 최종 답변 전송 완료

### 6. Clarify 루프 (Streaming STT)
- ✅ [단계 13] Streaming STT 결과 수신 완료
- ✅ [단계 13-2] Hybrid Search + Rerank 완료
- ✅ [단계 13-3] Evidence Check 완료
- ✅ [단계 13-4] Clarify 질문 생성 완료 (RED/YELLOW)
- ✅ [단계 13-5] LLM 답변 생성 완료 (RED/YELLOW)
- ✅ [단계 13-6] TTS 변환 완료 (RED/YELLOW)
- ✅ [단계 13-7] 모바일로 clarify_qa_turn 이벤트 전송 완료
- ✅ [단계 13-8] 최종 답변 생성 완료 (GPT-4o, GREEN)
- ✅ [단계 13-9] 최종 답변 TTS 변환 완료 (GREEN)
- ✅ [단계 13-10] 모바일로 final_answer 이벤트 전송 완료
- ✅ [단계 12-3] Clarify Q&A 턴 TTS 재생 완료 처리

---

## ✅ 적용된 단계 (라즈베리파이 Python 3.10)

### 1. Wakeword 감지
- ✅ [단계 2] Wakeword 감지 완료
- ✅ [단계 2-1] Wakeword 감지 이벤트 전송 완료
- ✅ [단계 2-2] 모바일 음성 파일 재생 완료

### 2. 버퍼링 STT
- ✅ [단계 3] 버퍼링 STT 세션 시작
- ✅ [완료] STT 세션 종료

### 3. Streaming STT 시작
- ✅ [단계 12-3] Streaming STT 시작 명령 수신
- ✅ [단계 12-4] 마이크 활성화 완료

---

## 📊 적용 현황 요약

### FastAPI 서버
- **총 적용 단계**: 30개
- **적용 위치**: `ai_server/rag_server/app/sockets/socket_handler.py`
- **함수명**: `wait_for_next_step(step_name, step_number)`

### 라즈베리파이 Python 3.10
- **총 적용 단계**: 6개
- **적용 위치**: `ai_raspi/AI_Supporter/main_py310.py`
- **함수명**: `wait_for_next_step_sync(step_name, step_number)`

### 라즈베리파이 Python 3.13
- **적용 없음**: 이벤트 수신 및 브리지 서버 전달 역할만 수행
- **이유**: 실제 로직은 Python 3.10에서 실행되므로 디버그 모드 불필요

---

## 🔍 주요 플로우별 디버그 모드 적용

### ✅ Wakeword → Intent 분류
```
[단계 2-1] Wakeword 감지 이벤트 수신
[단계 2-1-1] 모바일로 전송
[단계 2-2] 모바일 재생 완료 이벤트 수신
[단계 2-2-1] 라즈베리파이로 전송
[단계 6] STT 결과 수신
[단계 7] Intent 분류
[단계 8] 모바일로 Intent 결과 전송
[단계 8-1] 모바일 Intent 음성 재생 완료
```

### ✅ CV 탐지 성공 → RAG 답변
```
[단계 9] CV 모델 실행 완료
[단계 10] RAG 쿼리 생성
[단계 11] RAG 검색
[단계 12] GPT-4o 답변 생성
[단계 13] TTS 변환
[단계 14] 모바일로 전송
```

### ✅ CV 탐지 실패 → Clarify 루프
```
[단계 9] CV 모델 실행 완료 (탐지 실패)
[단계 10] 모바일로 cv_detection_failed 전송
[단계 11] 라즈베리파이로 cv_detection_failed 전송
[단계 12-1] 모바일 오디오 재생 완료 이벤트 수신
[단계 12-2] 라즈베리파이로 Streaming STT 시작 신호 전송
[단계 13] Streaming STT 결과 수신
[단계 13-2] Hybrid Search + Rerank
[단계 13-3] Evidence Check
[단계 13-4] Clarify 질문 생성 (RED/YELLOW)
[단계 13-5] LLM 답변 생성 (RED/YELLOW)
[단계 13-6] TTS 변환 (RED/YELLOW)
[단계 13-7] 모바일로 clarify_qa_turn 전송
[단계 12-3] Clarify Q&A 턴 TTS 재생 완료 처리
[단계 13-8] 최종 답변 생성 (GREEN)
[단계 13-9] 최종 답변 TTS 변환 (GREEN)
[단계 13-10] 모바일로 final_answer 전송
```

---

## 🎯 디버그 모드 활성화 방법

### 1. FastAPI 서버
```bash
# .env 파일 또는 환경 변수
DEBUG_STEP_BY_STEP=True
```

각 단계 완료 후:
```bash
# 다음 단계 진행
touch /tmp/next_step

# 자동 모드 활성화 (이후 단계 자동 진행)
echo 'auto' > /tmp/next_step
```

### 2. 라즈베리파이 Python 3.10
```bash
# config/settings.py 또는 환경 변수
DEBUG_STEP_BY_STEP=True
```

각 단계 완료 후:
- Enter 키 입력
- `auto` 입력 후 Enter (자동 모드 활성화)

---

## 📝 주의사항

1. **파일 트리거 방식 (FastAPI)**
   - `/tmp/next_step` 파일이 생성될 때까지 대기
   - 타임아웃: 300초 (5분)
   - 자동 모드: 파일 내용이 `auto`이면 이후 단계 자동 진행

2. **키보드 입력 방식 (라즈베리파이)**
   - Enter 키 입력 대기
   - 자동 모드: `auto` 입력 시 이후 단계 자동 진행
   - 백그라운드 실행 시 자동 진행

3. **비활성화 시**
   - `DEBUG_STEP_BY_STEP=False`일 때는 각 단계마다 0.5초 딜레이만 적용

---

## ✅ 최종 확인

**모든 주요 단계에 디버그 모드가 적용되어 있습니다!**

- ✅ Wakeword 감지 플로우
- ✅ Intent 분류 플로우
- ✅ CV 로직 실행
- ✅ CV 탐지 성공 → RAG 답변 생성
- ✅ CV 탐지 실패 → Clarify 루프
- ✅ Clarify Q&A 턴 처리
- ✅ 최종 답변 생성 및 전송

**문서 작성일**: 2025-01-XX
**최종 업데이트**: audio_playback_completed 핸들러에 디버그 모드 추가 완료

