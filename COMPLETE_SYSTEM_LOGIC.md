# 🎯 전체 시스템 로직 정리

## 📋 목차
1. [서버 시작 및 백그라운드 프로세스](#1-서버-시작-및-백그라운드-프로세스)
2. [Wakeword 감지 → Intent 분류 플로우](#2-wakeword-감지--intent-분류-플로우)
3. [AI_SUPPORTER Intent → CV 로직 실행](#3-ai_supporter-intent--cv-로직-실행)
4. [CV 탐지 성공 → RAG 기반 답변 생성](#4-cv-탐지-성공--rag-기반-답변-생성)
5. [CV 탐지 실패 → Clarify 루프](#5-cv-탐지-실패--clarify-루프)
6. [Clarify 루프 상세 플로우](#6-clarify-루프-상세-플로우)
7. [이벤트 기반 통신 흐름](#7-이벤트-기반-통신-흐름)

---

## 1. 서버 시작 및 백그라운드 프로세스

### 1.1 FastAPI 서버 시작
```
[FastAPI 서버 시작]
  ↓
[Socket.IO 서버 초기화]
  ↓
[이벤트 핸들러 등록]
  ├─ connect/disconnect
  ├─ register_device
  ├─ wakeword_detected
  ├─ wakeword_audio_completed
  ├─ intent_audio_completed
  ├─ audio_playback_completed
  ├─ stt_result
  ├─ video_frame
  └─ ...
  ↓
[CV 백그라운드 태스크 시작]
```

### 1.2 CV 백그라운드 장비 타입 감지
```
[background_device_detector() 실행]
  ↓
[2초 주기로 Redis 프레임 확인]
  ↓
[YOLO 모델로 장비 타입 감지]
  ├─ AHU
  ├─ FCU
  └─ unknown
  ↓
[current_device_type 전역변수에 저장]
  ↓
[다른 CV 모듈에서 참조 가능]
```

**구현 위치:**
- `ai_server/rag_server/app/services/cv/device_monitor.py`
- `ai_server/rag_server/app/sockets/socket_handler.py` (서버 시작 시)

---

## 2. Wakeword 감지 → Intent 분류 플로우

### 2.1 라즈베리파이: Wakeword 감지
```
[라즈베리파이 Python 3.10]
  ↓
[마이크 ON, Wakeword 감지 대기]
  ↓
[Wakeword 감지 ("onAir")]
  ↓
[브리지 서버로 wakeword_detected 이벤트 전송]
  ↓
[Python 3.13 → FastAPI → 모바일]
```

**구현 위치:**
- `ai_raspi/AI_Supporter/main_py310.py` (run_stt_loop)
- `ai_raspi/AI_Supporter/bridge/stt_bridge_server.py`
- `ai_raspi/AI_Supporter/stt/socketio_client.py`

### 2.2 모바일: Wakeword 음성 파일 재생
```
[모바일: wakeword_detected 이벤트 수신]
  ↓
[로컬 음성 파일 재생]
  └─ "001_onAir_서비스를_시작합니다_어떤_것을_도와드릴까요.mp3"
  ↓
[재생 완료]
  ↓
[FastAPI로 wakeword_audio_completed 이벤트 전송]
```

**구현 위치:**
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt` (handleWakewordDetected)
- `mobile/app/src/main/java/com/onair/mobile/assistant/data/stt/SocketIoSttClient.kt`

### 2.3 라즈베리파이: 버퍼링 STT 실행
```
[FastAPI: wakeword_audio_completed 이벤트 수신]
  ↓
[라즈베리파이로 버퍼링 STT 시작 신호]
  ↓
[라즈베리파이 Python 3.10]
  ↓
[4초간 음성 수집 (settings.STT_BUFFER_DURATION_SEC)]
  ↓
[GCP STT API 호출]
  ↓
[STT 결과 → 브리지 서버 → FastAPI]
  └─ stt_result 이벤트 (type="final")
```

**구현 위치:**
- `ai_raspi/AI_Supporter/main_py310.py` (버퍼링 STT)
- `ai_raspi/AI_Supporter/stt/gcp_stt_buffered.py`
- `ai_server/rag_server/app/sockets/socket_handler.py` (handle_stt_result)

### 2.4 FastAPI: Intent 분류
```
[FastAPI: stt_result 이벤트 수신]
  ↓
[Gemini-Flash로 Intent 분류]
  ├─ AI_SUPPORTER
  └─ OPERATOR
  ↓
[모바일로 intent_result 이벤트 전송]
```

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py` (handle_stt_result)
- `ai_server/rag_server/app/services/intent_service.py`

### 2.5 모바일: Intent별 음성 파일 재생
```
[모바일: intent_result 이벤트 수신]
  ↓
[Intent 타입 확인]
  ├─ AI_SUPPORTER
  │   └─ "001_AI_Supporter_기능을_시작합니다_오류_탐지.mp3" 재생
  └─ OPERATOR
      └─ (별도 처리)
  ↓
[재생 완료]
  ↓
[FastAPI로 intent_audio_completed 이벤트 전송]
```

**구현 위치:**
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt` (handleIntentResult)

---

## 3. AI_SUPPORTER Intent → CV 로직 실행

### 3.1 FastAPI: CV 모델 실행
```
[FastAPI: intent_audio_completed 이벤트 수신]
  ↓
[Intent == "AI_SUPPORTER" 확인]
  ↓
[Redis에서 최근 프레임 가져오기 (최대 20프레임)]
  ↓
[run_cv_model(frames) 실행]
  ├─ current_device_type 참조 (백그라운드에서 감지한 값)
  ├─ 프레임 선명도 계산 및 필터링
  ├─ 모듈 탐지 (fan, belt, gauge, panel)
  └─ 이상 탐지 (fan/belt, gauge, panel 병렬)
  ↓
[CV 결과 반환]
  ├─ detected: True/False
  ├─ device_type: "AHU" | "FCU" | "unknown"
  ├─ modules: ["fan", "belt", ...]
  ├─ anomalies: {...}
  └─ message: "이상이 감지되었습니다." | "탐지된 이상이 없습니다."
```

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py` (handle_intent_audio_completed)
- `ai_server/rag_server/app/services/cv_service.py` (run_cv_model)
- `ai_server/rag_server/app/services/cv/device_monitor.py` (background_device_detector)

---

## 4. CV 탐지 성공 → RAG 기반 답변 생성

### 4.1 CV 탐지 결과 기반 RAG 쿼리 생성
```
[CV 탐지 성공]
  ↓
[오류 내용 추출]
  ├─ device_type: "AHU"
  ├─ anomalies: {status: "anomaly_detected", results: {...}}
  └─ modules: ["fan", "belt"]
  ↓
[RAG 쿼리 생성]
  └─ 예: "AHU에서 fan, belt에서 이상이 탐지되었습니다"
```

### 4.2 RAG 검색
```
[RAG 검색 시작]
  ↓
[Hybrid Retrieve]
  └─ top_k=8 (기본값)
  ↓
[Rerank]
  └─ top_k=6 (기본값)
  ↓
[상위 5개 문서 선택]
```

**구현 위치:**
- `ai_server/rag_server/app/services/retrieve_service.py`
- `ai_server/rag_server/app/sockets/socket_handler.py` (CV 탐지 성공 분기)

### 4.3 GPT-4o로 최종 답변 생성
```
[GPT-4o API 호출]
  ↓
[구조화된 답변 생성]
  ├─ summary: "문제 요약"
  ├─ possible_causes: ["원인 1", "원인 2", ...]
  ├─ diagnosis_steps: [{step, action, method, expected_result}, ...]
  ├─ recommended_actions: [{priority, action, safety_note}, ...]
  ├─ safety_warnings: ["주의사항 1", ...]
  └─ tts_text: "TTS 친화적 텍스트"
```

**구현 위치:**
- `ai_server/rag_server/app/services/generator.py` (llm_generate_answer)

### 4.4 TTS 변환
```
[TTS 변환]
  ↓
[GCP Text-to-Speech API 호출]
  ↓
[Base64 인코딩된 오디오 생성]
  ├─ audio_content: "base64_string"
  └─ audio_encoding: "audio/mpeg"
```

**구현 위치:**
- `ai_server/rag_server/app/services/tts_service.py`

### 4.5 모바일로 최종 답변 전송
```
[모바일로 final_answer 이벤트 전송]
  ├─ answer: "TTS 친화적 텍스트"
  ├─ structured_answer: {전체 구조화된 답변}
  ├─ audio_content: "base64_string"
  ├─ audio_encoding: "audio/mpeg"
  ├─ citations: [{section, pages, excerpt}, ...]
  └─ cv_detection_result: {device_type, modules, anomalies, message}
  ↓
[모바일: 화면 표시 + TTS 재생]
```

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py` (CV 탐지 성공 분기)
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt` (handleFinalAnswerFromSocket)

---

## 5. CV 탐지 실패 → Clarify 루프

### 5.1 모바일: CV 탐지 실패 음성 파일 재생
```
[FastAPI: cv_detection_failed 이벤트 전송]
  ↓
[모바일: cv_detection_failed 이벤트 수신]
  ↓
[로컬 음성 파일 재생]
  └─ "001_오류를_탐지하지_못했습니다_AI_Supporter와의.mp3"
  ↓
[재생 완료]
  ↓
[FastAPI로 audio_playback_completed 이벤트 전송]
  └─ type="cv_detection_failed"
```

**구현 위치:**
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt` (handleCvDetectionFailed)
- `mobile/app/src/main/java/com/onair/mobile/assistant/data/stt/SocketIoSttClient.kt`

### 5.2 라즈베리파이: Streaming STT 세션 시작
```
[FastAPI: audio_playback_completed 이벤트 수신 (type="cv_detection_failed")]
  ↓
[라즈베리파이로 start_streaming_stt 이벤트 전송]
  ├─ session_id: "uuid"
  └─ message: "Streaming STT 세션을 시작하세요."
  ↓
[라즈베리파이 Python 3.13: start_streaming_stt 이벤트 수신]
  ↓
[브리지 서버로 Streaming STT 시작 명령 전송]
  ↓
[라즈베리파이 Python 3.10: Streaming STT 세션 시작]
  ├─ 마이크 활성화
  └─ 실시간 Streaming STT 시작
```

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py` (handle_audio_playback_completed)
- `ai_raspi/AI_Supporter/stt/socketio_client.py` (handle_start_streaming_stt)
- `ai_raspi/AI_Supporter/main_py310.py` (start_streaming_stt)

---

## 6. Clarify 루프 상세 플로우

### 6.1 사용자 침묵 감지 → 질문 1개 전송
```
[라즈베리파이: Streaming STT 실행 중]
  ↓
[사용자 발화 중]
  ├─ interim 결과: 실시간 인식 텍스트
  └─ final 결과: GCP STT가 final 반환
  ↓
[침묵 감지 (SILENCE_TIMEOUT_SEC = 0.5초)]
  ├─ 마지막 interim 결과 사용
  └─ 강제 final 이벤트 발생
  ↓
[브리지 서버 → FastAPI: stt_result 이벤트 전송]
  ├─ type: "final"
  ├─ text: "사용자 질문"
  ├─ confidence: 0.95
  └─ session_id: "uuid"
```

**구현 위치:**
- `ai_raspi/AI_Supporter/stt/gcp_stt_stream.py` (_monitor_silence)
- `ai_server/rag_server/app/sockets/socket_handler.py` (handle_stt_result)

### 6.2 FastAPI: Clarify Q&A 턴 처리
```
[FastAPI: stt_result 이벤트 수신 (session_id 있음)]
  ↓
[process_clarify_qa_turn(session_id, user_question) 호출]
  ↓
[1. 히스토리 컨텍스트 구성]
  ├─ 최근 사용자 질문 2개
  └─ 최근 Clarify 질문/답변 2개
  ↓
[2. Hybrid Search + Rerank]
  ├─ Hybrid Retrieve (top_k=8)
  └─ Rerank (top_k=6)
  ↓
[3. Evidence Check (RED/YELLOW/GREEN)]
  ├─ RED: 증거 부족
  ├─ YELLOW: 증거 부분적
  └─ GREEN: 증거 충분
```

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py` (process_clarify_qa_turn)
- `ai_server/rag_server/app/services/answerability.py` (comprehensive_evidence_check)

### 6.3 RED/YELLOW → Clarify 질문 생성
```
[Evidence Check 결과: RED 또는 YELLOW]
  ↓
[Clarify 질문 생성 (Gemini-Flash)]
  └─ make_clarify_prompt()
  ↓
[LLM 답변 생성 (Gemini-Flash)]
  └─ "문제 상황을 구체적으로 말씀해주세요."
  ↓
[TTS 변환]
  ↓
[모바일로 clarify_qa_turn 이벤트 전송]
  ├─ session_id
  ├─ turn_id
  ├─ user_question: "사용자 질문"
  ├─ llm_answer: "LLM 답변"
  ├─ audio_content: "base64_string"
  ├─ audio_encoding: "audio/mpeg"
  ├─ need_clarify: True
  └─ gate_decision: "RED" | "YELLOW"
```

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py` (process_clarify_qa_turn, RED/YELLOW 분기)
- `ai_server/rag_server/app/services/answerability.py` (make_clarify_prompt)

### 6.4 모바일: Clarify Q&A 턴 TTS 재생
```
[모바일: clarify_qa_turn 이벤트 수신]
  ↓
[화면에 질문/답변 표시]
  ├─ 질문: user_question
  └─ 답변: llm_answer
  ↓
[TTS 음성 파일 재생]
  ↓
[재생 완료]
  ↓
[FastAPI로 audio_playback_completed 이벤트 전송]
  └─ type="clarify_qa_turn", session_id, turn_id
  ↓
[FastAPI: 다음 Streaming STT 질문 대기]
```

**구현 위치:**
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt` (handleClarifyQaTurn)
- `ai_server/rag_server/app/sockets/socket_handler.py` (handle_audio_playback_completed)

### 6.5 GREEN → 최종 답변 생성
```
[Evidence Check 결과: GREEN]
  ↓
[GPT-4o로 최종 답변 생성]
  ├─ 구조화된 답변 생성
  └─ TTS 친화적 텍스트 생성
  ↓
[TTS 변환]
  ↓
[모바일로 final_answer 이벤트 전송]
  ├─ session_id
  ├─ turn_id
  ├─ answer: "최종 답변 텍스트"
  ├─ structured_answer: {전체 구조화된 답변}
  ├─ audio_content: "base64_string"
  ├─ audio_encoding: "audio/mpeg"
  └─ citations: [{section, pages}, ...]
  ↓
[라즈베리파이로 stop_streaming_stt 이벤트 전송]
  └─ session_id, reason="final_answer_completed"
```

**구현 위치:**
- `ai_server/rag_server/app/sockets/socket_handler.py` (process_clarify_qa_turn, GREEN 분기)
- `ai_server/rag_server/app/routers/clarify_router.py` (process_clarify_turn)

### 6.6 모바일: 최종 답변 표시 및 재생
```
[모바일: final_answer 이벤트 수신]
  ↓
[화면에 최종 답변 표시]
  └─ answer 또는 structured_answer
  ↓
[TTS 음성 파일 재생]
  ↓
[재생 완료]
  ↓
[세션 초기화]
  ├─ isWaitingForClarification = false
  ├─ currentSessionId = null
  └─ currentTurnId = 1
```

**구현 위치:**
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt` (handleFinalAnswerFromSocket)

---

## 7. 이벤트 기반 통신 흐름

### 7.1 주요 Socket.IO 이벤트

#### 라즈베리파이 → FastAPI
- `register_device`: 디바이스 등록
- `wakeword_detected`: Wakeword 감지
- `stt_result`: STT 결과 (버퍼링/스트리밍)
- `video_frame`: 비디오 프레임

#### 모바일 → FastAPI
- `register_device`: 디바이스 등록
- `wakeword_audio_completed`: Wakeword 음성 파일 재생 완료
- `intent_audio_completed`: Intent 음성 파일 재생 완료
- `audio_playback_completed`: 오디오 재생 완료 (CV 탐지 실패, Clarify Q&A 턴)

#### FastAPI → 라즈베리파이
- `cv_detection_failed`: CV 탐지 실패
- `cv_detection_success`: CV 탐지 성공
- `start_streaming_stt`: Streaming STT 시작 신호
- `stop_streaming_stt`: Streaming STT 종료 신호
- `service_completed`: 서비스 완료

#### FastAPI → 모바일
- `wakeword_detected`: Wakeword 감지 알림
- `intent_result`: Intent 분류 결과
- `cv_detection_failed`: CV 탐지 실패
- `cv_detection_success`: CV 탐지 성공
- `clarify_qa_turn`: Clarify 질문/답변 턴
- `final_answer`: 최종 답변

### 7.2 이벤트 흐름 다이어그램

```
[Wakeword 감지]
  라즈베리파이 → FastAPI → 모바일
  모바일 → FastAPI (재생 완료)
  FastAPI → 라즈베리파이 (버퍼링 STT 시작)

[Intent 분류]
  라즈베리파이 → FastAPI (STT 결과)
  FastAPI → 모바일 (Intent 결과)
  모바일 → FastAPI (재생 완료)
  FastAPI → 라즈베리파이 (CV 로직 실행)

[CV 탐지 성공]
  FastAPI → 모바일 (최종 답변)

[CV 탐지 실패]
  FastAPI → 모바일 (탐지 실패)
  모바일 → FastAPI (재생 완료)
  FastAPI → 라즈베리파이 (Streaming STT 시작)

[Clarify 루프]
  라즈베리파이 → FastAPI (사용자 질문)
  FastAPI → 모바일 (Clarify 질문/답변 또는 최종 답변)
  모바일 → FastAPI (재생 완료)
  (반복 또는 종료)
```

---

## 8. 주요 컴포넌트 위치

### 8.1 FastAPI 서버
- **Socket.IO 핸들러**: `ai_server/rag_server/app/sockets/socket_handler.py`
- **CV 서비스**: `ai_server/rag_server/app/services/cv_service.py`
- **RAG 검색**: `ai_server/rag_server/app/services/retrieve_service.py`
- **답변 생성**: `ai_server/rag_server/app/services/generator.py`
- **TTS 서비스**: `ai_server/rag_server/app/services/tts_service.py`
- **Intent 분류**: `ai_server/rag_server/app/services/intent_service.py`

### 8.2 라즈베리파이
- **메인 STT 루프**: `ai_raspi/AI_Supporter/main_py310.py`
- **버퍼링 STT**: `ai_raspi/AI_Supporter/stt/gcp_stt_buffered.py`
- **스트리밍 STT**: `ai_raspi/AI_Supporter/stt/gcp_stt_stream.py`
- **Socket.IO 클라이언트**: `ai_raspi/AI_Supporter/stt/socketio_client.py`
- **브리지 서버**: `ai_raspi/AI_Supporter/bridge/stt_bridge_server.py`
- **브리지 클라이언트**: `ai_raspi/AI_Supporter/bridge/stt_bridge_client.py`

### 8.3 모바일 앱
- **메인 액티비티**: `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt`
- **Socket.IO 클라이언트**: `mobile/app/src/main/java/com/onair/mobile/assistant/data/stt/SocketIoSttClient.kt`
- **TTS Repository**: `mobile/app/src/main/java/com/onair/mobile/assistant/data/tts/TtsRepositoryImpl.kt`
- **MediaPlayer 컨트롤러**: `mobile/app/src/main/java/com/onair/mobile/assistant/data/tts/MediaPlayerController.kt`

---

## 9. 주요 설정값

### 9.1 STT 설정
- `STT_BUFFER_DURATION_SEC`: 버퍼링 STT 음성 수집 시간 (4초)
- `SILENCE_TIMEOUT_SEC`: 침묵 타임아웃 (0.5초)

### 9.2 RAG 설정
- `TOP_K`: Hybrid Retrieve 상위 K개 (8)
- `RERANK_TOP_K`: Rerank 상위 K개 (6)
- `USED_HITS`: 최종 사용 문서 수 (5)

### 9.3 CV 설정
- `FRAME_LIMIT`: Redis에서 가져올 최대 프레임 수 (20)
- `DEVICE_DETECTION_INTERVAL`: 장비 타입 감지 주기 (2초)

---

## 10. 전체 플로우 요약

```
[서버 시작]
  ├─ FastAPI 서버 시작
  ├─ Socket.IO 서버 초기화
  └─ CV 백그라운드 장비 타입 감지 시작

[Wakeword 감지]
  ├─ 라즈베리파이: Wakeword 감지
  ├─ 모바일: 음성 파일 재생
  └─ 라즈베리파이: 버퍼링 STT 실행

[Intent 분류]
  ├─ FastAPI: Gemini-Flash로 Intent 분류
  └─ 모바일: Intent별 음성 파일 재생

[AI_SUPPORTER Intent]
  ├─ FastAPI: CV 모델 실행
  │
  ├─ [CV 탐지 성공]
  │   ├─ RAG 쿼리 생성
  │   ├─ RAG 검색
  │   ├─ GPT-4o로 최종 답변 생성
  │   ├─ TTS 변환
  │   └─ 모바일로 최종 답변 전송
  │
  └─ [CV 탐지 실패]
      ├─ 모바일: 탐지 실패 음성 파일 재생
      ├─ 라즈베리파이: Streaming STT 세션 시작
      └─ Clarify 루프 시작
          ├─ 사용자 침묵 감지 → 질문 전송
          ├─ Evidence Check (RED/YELLOW/GREEN)
          ├─ RED/YELLOW: Clarify 질문 생성 → TTS → 모바일 전송
          ├─ 모바일: TTS 재생 완료 → 다음 질문 대기
          └─ GREEN: GPT-4o 최종 답변 생성 → TTS → 모바일 전송
```

---

## 11. 주요 특징

### 11.1 이벤트 기반 아키텍처
- 모든 통신이 Socket.IO 이벤트 기반
- 비동기 처리로 응답성 향상
- 재생 완료 이벤트로 정확한 타이밍 제어

### 11.2 백그라운드 CV 모니터링
- 서버 시작 시 자동으로 장비 타입 감지 시작
- 2초 주기로 Redis 프레임 확인
- 전역 변수로 다른 CV 모듈에서 참조 가능

### 11.3 RAG 기반 답변 생성
- Hybrid Retrieve + Rerank로 정확한 문서 검색
- Evidence Check로 답변 가능 여부 판단
- GPT-4o로 구조화된 답변 생성
- TTS 친화적 텍스트 자동 변환

### 11.4 Clarify 루프
- 사용자 침묵 감지로 자연스러운 질문 단위 구분
- 히스토리 컨텍스트 반영으로 연속 대화 지원
- RED/YELLOW/GREEN 게이트로 단계적 답변 생성
- Gemini-Flash와 GPT-4o의 역할 분리

---

**문서 작성일**: 2025-01-XX
**최종 업데이트**: CV 탐지 성공 시 RAG 기반 답변 생성 로직 추가 완료

