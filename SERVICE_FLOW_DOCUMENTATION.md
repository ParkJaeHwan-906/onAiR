# 🎯 Wakeword부터 서비스 종료까지 전체 플로우 문서

## 📋 목차
1. [전체 플로우 개요](#전체-플로우-개요)
2. [단계별 상세 플로우](#단계별-상세-플로우)
3. [분기별 처리 로직](#분기별-처리-로직)
4. [코드 구현 위치](#코드-구현-위치)

---

## 전체 플로우 개요

```
① 대기 상태 (마이크 ON, Wakeword 감지 중)
    ↓
② Wakeword 감지 ("onAir")
    ↓
③ 버퍼링 STT 실행 (3~5초 음성 수집)
    ↓
④ STT 텍스트 전송 → 마이크 OFF, 버퍼링 STT 세션 종료
    ↓
⑤ Intent 분류 (Gemini-Flash)
    ↓
⑥ 분기 처리
    ├─ OPERATOR → WebRTC 연결
    │   └─ 마이크 OFF 유지, STT 세션 종료 상태 유지
    └─ AI_SUPPORTER → CV 모델 실행
        ├─ CV 성공 → (TODO: 처리 로직)
        └─ CV 실패 → 마이크 ON, Streaming STT 즉시 시작
            ↓
⑦ Clarify 루프 (질문/답변 반복)
    ├─ RED/YELLOW → Clarify 질문 생성
    └─ GREEN → 최종 답변 생성
    ↓
⑧ 서비스 종료 → 마이크 ON 유지 (다음 Wakeword 대기)
```

---

## 단계별 상세 플로우

### ① 대기 상태 (마이크 ON, Wakeword 감지 중)

**라즈베리파이 (`ai_raspi/AI_Supporter/main.py`)**
- 마이크 스트림 항상 활성화 (`MicStream.start()`)
- Wakeword 감지기 실행 (`init_wakeword_detector()`)
- Socket.IO 서버 연결 및 디바이스 등록 (`raspi`)

**구현 위치:**
- `ai_raspi/AI_Supporter/main.py:34-73`
- `ai_raspi/AI_Supporter/stt/wakeword_detector.py`

---

### ② Wakeword 감지

**라즈베리파이 (`ai_raspi/AI_Supporter/stt/wakeword_detector.py`)**
- "onAir" 키워드 감지 (ONNX 모델 사용)
- 신뢰도 임계값 초과 시 감지 성공
- `wait_for_wakeword()` 반환

**구현 위치:**
- `ai_raspi/AI_Supporter/stt/wakeword_detector.py:106-154`
- `ai_raspi/AI_Supporter/main.py:124`

---

### ③ 버퍼링 STT 실행

**라즈베리파이 (`ai_raspi/AI_Supporter/stt/gcp_stt_buffered.py`)**
- 마이크로부터 3~5초 음성 수집 (`STT_BUFFER_DURATION_SEC`)
- GCP Speech-to-Text API 호출
- `type="final"` STT 결과 생성
- Socket.IO로 `stt_result` 이벤트 전송 (session_id 없음)

**전송 데이터:**
```json
{
  "type": "final",
  "text": "에러가 발생했어요",
  "confidence": 0.95
}
```

**구현 위치:**
- `ai_raspi/AI_Supporter/stt/gcp_stt_buffered.py`
- `ai_raspi/AI_Supporter/main.py:86-90`

**중요:** 버퍼링 STT 완료 후 마이크는 자동으로 OFF됨 (`buffered_stt.run()` 내부)

---

### ④ STT 텍스트 전송, 마이크 OFF, 버퍼링 STT 세션 종료

**라즈베리파이 (`ai_raspi/AI_Supporter/stt/gcp_stt_buffered.py`)**
- 버퍼링 STT 완료 후 마이크 OFF (`mic.pause()`)
- 버퍼링 STT 세션 종료

**FastAPI 서버 (`ai_server/rag_server/app/sockets/socket_handler.py`)**
- 라즈베리파이로부터 `stt_result` 이벤트 수신
- `type="final"`이고 `session_id`가 없으면 버퍼링 STT로 판단

**처리:**
1. 모바일로 `start_sse_connection` 이벤트 전송
2. Gemini-Flash로 Intent 분류 시작

**구현 위치:**
- `ai_raspi/AI_Supporter/stt/gcp_stt_buffered.py:150-152`
- `ai_server/rag_server/app/sockets/socket_handler.py:144-237`

---

### ⑤ Intent 분류 (Gemini-Flash)

**FastAPI 서버 (`ai_server/rag_server/app/services/intent_service.py`)**
- Gemini-1.5-Flash 모델 사용
- 사용자 입력을 분석하여 두 가지 중 하나로 분류:
  - **OPERATOR**: 사람 오퍼레이터 연결 필요
  - **AI_SUPPORTER**: AI 서포터가 처리 가능

**분류 결과:**
```json
{
  "intent": "AI_SUPPORTER" | "OPERATOR",
  "confidence": 0.0~1.0,
  "reasoning": "판단 근거"
}
```

**모바일로 전송:**
- Socket.IO `intent_result` 이벤트로 전송

**구현 위치:**
- `ai_server/rag_server/app/services/intent_service.py:22-114`
- `ai_server/rag_server/app/sockets/socket_handler.py:178-189`

---

## 분기별 처리 로직

### 분기 1: OPERATOR

**모바일 (`mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt`)**

1. **TTS 재생**: "통신이 시작됩니다."
2. **UI 업데이트**: "통신 중..." 화면 표시
3. **WebRTC 연결 요청**: Spring 서버로 WebRTC 연결 요청
4. **라즈베리파이 제어**: `notifyIntentDone("OPERATOR")` 전송

**라즈베리파이 (`ai_raspi/AI_Supporter/stt/socketio_client.py`)**
- `control_raspi` 이벤트 수신 (`command="notify_intent_done"`)
- `branch="OPERATOR"`인 경우:
  - STT 모드 `buffered` 유지
  - **마이크 OFF 상태 유지** (버퍼링 STT 후 이미 OFF됨)
  - **STT 세션 종료 상태 유지** (버퍼링 STT 세션 종료됨)
  - `resume()` 호출하지 않음

**구현 위치:**
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt:214-242`
- `ai_raspi/AI_Supporter/stt/socketio_client.py:144-154`

**종료 조건:**
- WebRTC 연결 종료 시 서비스 종료
- 마이크는 OFF 상태 유지, STT 세션 종료 상태 유지
- 다음 Wakeword 감지 시 다시 버퍼링 STT 시작

---

### 분기 2: AI_SUPPORTER

#### 2-1. 모바일 UI 업데이트

**모바일 (`mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt`)**

1. **TTS 재생**: "AI_SUPPORTER가 도와드리겠습니다"
2. **UI 업데이트**: "AI_SUPPORTER on" 화면 표시
3. **2초 후**: "오류 분석 중입니다. 움직이지 말아주세요." 화면 표시

**구현 위치:**
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt:195-212`

---

#### 2-2. CV 모델 실행

**FastAPI 서버 (`ai_server/rag_server/app/sockets/socket_handler.py`)**

- CV 모델 실행 (`run_cv_model()`)
- 오류 탐지 결과에 따라 분기:

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py:194-226`

---

#### 2-2-1. CV 모델 성공 (오류 탐지 성공)

**현재 상태:** TODO - 처리 로직 미구현

**예상 동작:**
- 탐지된 오류 타입 표시
- 관련 문서 검색 및 답변 생성
- (구현 필요)

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py:214-216` (TODO 주석)

---

#### 2-2-2. CV 모델 실패 (오류 탐지 실패)

**FastAPI 서버**
- 모바일과 라즈베리파이로 `cv_detection_failed` 이벤트 전송

**모바일 (`mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt`)**
- `cv_detection_failed` 이벤트 수신
- UI 업데이트: "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다. 문제 상황을 구체적으로 말씀해주세요."

**라즈베리파이 (`ai_raspi/AI_Supporter/stt/socketio_client.py`)**
- `cv_detection_failed` 이벤트 수신
- **마이크 ON** (`mic.resume()`)
- **Streaming STT 즉시 시작** (별도 태스크로 실행)
- 세션 ID 생성 및 Clarify 루프 시작

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py:198-226`
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt:316-332` (cv_detection_failed 핸들러)
- `ai_raspi/AI_Supporter/stt/socketio_client.py:89-132` (cv_detection_failed 핸들러)

**다음 단계:** Clarify 루프 시작 (Streaming STT로 사용자 질문 수집)

---

#### 2-3. Streaming STT 시작

**라즈베리파이 (`ai_raspi/AI_Supporter/stt/socketio_client.py`)**

CV 실패 시 즉시 실행:
1. **모드 전환**: `manager.set_stt_mode("streaming")`
2. **마이크 활성화**: `mic.resume()` (버퍼링 STT 후 OFF되었으므로)
3. **세션 ID 생성**: UUID 생성 (Clarify 세션용)
4. **Streaming STT 즉시 시작**: `asyncio.create_task(streaming_stt.run(...))` (별도 태스크로 실행)

**또는 Wakeword 감지 시 (`ai_raspi/AI_Supporter/main.py`):**
- 모드가 `streaming`이면 Streaming STT 실행

**Streaming STT 동작 (`ai_raspi/AI_Supporter/stt/gcp_stt_stream.py`)**
- 실시간 음성 인식 (GCP Streaming STT API)
- `type="interim"` 또는 `type="final"` 결과 생성
- Socket.IO로 `stt_result` 이벤트 전송 (session_id 포함)

**전송 데이터:**
```json
{
  "type": "interim" | "final",
  "text": "에러가 발생했어요",
  "confidence": 0.95,
  "session_id": "uuid-string"
}
```

**구현 위치:**
- `ai_raspi/AI_Supporter/main.py:91-110`
- `ai_raspi/AI_Supporter/stt/gcp_stt_stream.py`

---

#### 2-4. Clarify 루프 처리

**FastAPI 서버 (`ai_server/rag_server/app/sockets/socket_handler.py`)**

**Streaming STT 수신 처리:**
1. Redis 세션에 STT 텍스트 추가 (`memory.append_event()`)
2. `type="final"`이면 Clarify 처리 시작 (`process_clarify_qa_turn()`)

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py:239-256`

---

#### 2-4-1. Clarify 질문/답변 턴 처리

**FastAPI 서버 (`ai_server/rag_server/app/sockets/socket_handler.py:422-604`)**

**처리 단계:**

1. **Gemini-Flash로 clarify 여부 판단**
   - `clarify_query(user_question)` 호출
   - `need_clarify` 값 결정

2. **구체화 필요 시 (need_clarify=True)**
   - Clarify 질문 생성
   - Gemini-Flash로 LLM 답변 생성
   - TTS 변환
   - 모바일로 `clarify_qa_turn` 이벤트 전송

3. **충분히 구체화됨 (need_clarify=False)**
   - Hybrid Search + Rerank
   - GPT-4o로 최종 답변 생성
   - TTS 변환
   - 모바일로 `final_answer` 이벤트 전송
   - Redis 세션 초기화
   - 라즈베리파이로 `stop_streaming_stt` 이벤트 전송

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py:422-604`

---

#### 2-4-2. 모바일 Clarify 처리

**모바일 (`mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt`)**

**Clarify 질문/답변 턴 수신 (`clarify_qa_turn` 이벤트):**
- 질문과 LLM 답변 표시
- TTS 재생 (audio_content가 있는 경우)
- 사용자 입력 대기

**최종 답변 수신 (`final_answer` 이벤트):**
- 답변 텍스트 표시
- TTS 재생
- 세션 초기화
- UI 업데이트

**구현 위치:**
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt:371-415`

---

#### 2-5. Streaming STT 종료

**라즈베리파이 (`ai_raspi/AI_Supporter/stt/socketio_client.py`)**

- `stop_streaming_stt` 이벤트 수신
- `session_id` 확인
- Streaming STT 세션 종료 (`manager.add_stop_streaming_session(session_id)`)

**구현 위치:**
- `ai_raspi/AI_Supporter/stt/socketio_client.py:77-86`
- `ai_raspi/AI_Supporter/stt/gcp_stt_stream.py` (종료 로직)

---

### ⑧ 서비스 종료 및 대기 복귀

**라즈베리파이 (`ai_raspi/AI_Supporter/main.py`)**
- Streaming STT 종료 후 마이크는 계속 ON 상태 유지
- 다음 Wakeword 대기 상태로 복귀
- 루프 반복 (① 대기 상태로 복귀)

**구현 위치:**
- `ai_raspi/AI_Supporter/main.py:109-130`

---

## 코드 구현 위치 요약

### 라즈베리파이
- **메인 루프**: `ai_raspi/AI_Supporter/main.py`
- **Wakeword 감지**: `ai_raspi/AI_Supporter/stt/wakeword_detector.py`
- **버퍼링 STT**: `ai_raspi/AI_Supporter/stt/gcp_stt_buffered.py`
- **Streaming STT**: `ai_raspi/AI_Supporter/stt/gcp_stt_stream.py`
- **Socket.IO 클라이언트**: `ai_raspi/AI_Supporter/stt/socketio_client.py`

### FastAPI 서버
- **Socket.IO 핸들러**: `ai_server/rag_server/app/sockets/socket_handler.py`
- **Intent 분류**: `ai_server/rag_server/app/services/intent_service.py`
- **CV 모델**: `ai_server/rag_server/app/services/cv_service.py`
- **Clarify 처리**: `ai_server/rag_server/app/sockets/socket_handler.py:422-604`
- **RAG 검색**: `ai_server/rag_server/app/services/retrieve_service.py`
- **답변 생성**: `ai_server/rag_server/app/services/generator.py`

### 모바일
- **메인 Activity**: `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt`
- **Socket.IO 클라이언트**: `mobile/app/src/main/java/com/onair/mobile/assistant/data/stt/SocketIoSttClient.kt`
- **라즈베리파이 제어**: `mobile/app/src/main/java/com/onair/mobile/assistant/data/raspberry/RaspberryPiControlRepository.kt`

---

## 🔍 구현 상태 체크리스트

### ✅ 완료된 기능
- [x] Wakeword 감지
- [x] 버퍼링 STT
- [x] Intent 분류 (Gemini-Flash)
- [x] OPERATOR 분기 처리
- [x] AI_SUPPORTER 분기 처리
- [x] CV 모델 실행
- [x] CV 실패 시 Streaming STT 시작
- [x] Clarify 질문/답변 턴 처리
- [x] 최종 답변 생성
- [x] Streaming STT 종료

### ⚠️ 부분 구현 / TODO
- [ ] CV 모델 성공 시 처리 로직 (현재 TODO 주석만 있음)
- [ ] 라즈베리파이 `cv_detection_failed` 이벤트 핸들러 (현재 없음)
- [ ] Clarify 입력 텍스트 전송 (모바일 → FastAPI) - Socket.IO로 구현됨
- [ ] Clarify 세션 취소/건너뛰기 기능

### 📝 개선 필요 사항
- [ ] 에러 핸들링 강화
- [ ] 재연결 로직 개선
- [ ] 로깅 및 모니터링 강화
- [ ] 성능 최적화

---

## 🔄 이벤트 흐름도

### 버퍼링 STT → Intent 분류
```
라즈베리파이 → Socket.IO (stt_result)
    ↓
FastAPI 서버 (handle_stt_result)
    ├─ 모바일: start_sse_connection
    └─ Gemini-Flash: Intent 분류
        ↓
    모바일: intent_result
```

### AI_SUPPORTER → CV 모델 → Streaming STT
```
FastAPI 서버 (CV 모델 실행)
    ├─ CV 성공 → (TODO)
    └─ CV 실패 → cv_detection_failed
        ├─ 모바일: cv_detection_failed
        └─ 라즈베리파이: cv_detection_failed
            ↓
        라즈베리파이: Streaming STT 시작
            ↓
        Socket.IO (stt_result, session_id 포함)
            ↓
        FastAPI 서버: Clarify 처리
```

### Clarify 루프
```
Streaming STT (final) → FastAPI 서버
    ↓
process_clarify_qa_turn()
    ├─ need_clarify=True → clarify_qa_turn
    │   └─ 모바일: 질문 + LLM 답변 표시
    │       ↓
    │   사용자 입력 (Streaming STT)
    │       ↓
    │   (루프 반복)
    │
    └─ need_clarify=False → final_answer
        ├─ 모바일: 최종 답변 표시
        └─ 라즈베리파이: stop_streaming_stt
```

---

## 📌 주요 설계 결정사항

1. **마이크 상태 관리**
   - 마이크는 항상 ON 상태 유지
   - 버퍼링 STT 후 Intent 분류 중간에만 OFF
   - Streaming STT 시작 시 다시 ON

2. **Intent 분류 위치**
   - FastAPI 서버에서 Gemini-Flash로 분류
   - 모바일은 분류 결과만 수신하여 분기 처리

3. **CV 모델 실행 시점**
   - AI_SUPPORTER 분기에서만 실행
   - FastAPI 서버에서 실행 (라즈베리파이 카메라 이미지 필요 시 별도 처리)

4. **Clarify 루프**
   - Streaming STT 세션 중에만 실행
   - Redis 세션으로 히스토리 관리
   - 최종 답변 생성 시 세션 초기화

5. **통신 방식**
   - 모든 통신은 Socket.IO를 통해 이루어짐
   - FastAPI 서버가 중앙 허브 역할
   - 모바일과 라즈베리파이는 모두 클라이언트

