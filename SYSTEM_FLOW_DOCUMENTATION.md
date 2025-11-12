# 🏗️ 전체 시스템 통신 흐름 상세 문서

## 📋 목차
1. [시스템 아키텍처 개요](#시스템-아키텍처-개요)
2. [공통 로직: Wakeword 감지부터 버퍼링 STT까지](#공통-로직-wakeword-감지부터-버퍼링-stt까지)
3. [AI_SUPPORTER 분기](#ai_supporter-분기)
4. [OPERATOR 분기](#operator-분기)
5. [CV 탐지 실패 시 Clarify Q&A 흐름](#cv-탐지-실패-시-clarify-qa-흐름)
6. [CV 탐지 성공 시 최종 답변 흐름](#cv-탐지-성공-시-최종-답변-흐름)
7. [이벤트 목록 및 데이터 구조](#이벤트-목록-및-데이터-구조)

---

## 🏗️ 시스템 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│                    라즈베리파이 (Python 3.10)                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  main_py310.py                                       │  │
│  │  - Wakeword 감지 (Porcupine)                         │  │
│  │  - 버퍼링 STT (GCP Speech-to-Text)                  │  │
│  │  - 스트리밍 STT (GCP Streaming STT)                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          │ Socket.IO (로컬 브리지 서버)      │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  브리지 서버 (stt_bridge_server.py)                  │  │
│  │  - Python 3.10 ↔ Python 3.13 통신                   │  │
│  │  - 포트: 5050                                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          │ Socket.IO                        │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  브리지 클라이언트 (stt_bridge_client.py)             │  │
│  │  - Python 3.13에서 실행                               │  │
│  │  - FastAPI Socket.IO 클라이언트 연결                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Socket.IO (wss://onair.ai.kr/ws)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 서버                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  socket_handler.py                                    │  │
│  │  - Socket.IO 서버 (포트: /ws)                        │  │
│  │  - 디바이스 관리 (raspi, mobile)                     │  │
│  │  - 이벤트 라우팅                                     │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  서비스 레이어                                        │  │
│  │  - Intent 분류 (Gemini-Flash)                        │  │
│  │  - CV 모델 실행                                      │  │
│  │  - RAG 검색                                          │  │
│  │  - LLM 답변 생성 (GPT-4o)                           │  │
│  │  - TTS 변환                                          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Socket.IO (wss://onair.ai.kr/ws)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    모바일 앱 (Android)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MainActivitySttServer / WorkingActivity            │  │
│  │  - SocketIoSttClient                                 │  │
│  │  - MediaPlayerController (오디오 재생)               │  │
│  │  - UI 업데이트                                       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 공통 로직: Wakeword 감지부터 버퍼링 STT까지

### 단계별 상세 흐름

#### **단계 1: Wakeword 감지 대기**
```
[라즈베리파이 Python 3.10]
├─ 마이크 ON
├─ Wakeword 감지기 활성화 (Porcupine)
└─ 대기 중...
```

#### **단계 2: Wakeword 감지**
```
[라즈베리파이 Python 3.10]
├─ Wakeword 감지 ✅
├─ Wakeword 콜백 비활성화
├─ Wakeword 감지기 일시 중지
└─ 브리지 서버로 이벤트 전송
    │
    │ Socket.IO: wakeword_detected
    ▼
[브리지 서버 (stt_bridge_server.py)]
├─ Python 3.10 → Python 3.13으로 이벤트 전달
└─ 브리지 클라이언트로 전송
    │
    │ Socket.IO: wakeword_detected
    ▼
[브리지 클라이언트 (stt_bridge_client.py)]
├─ Python 3.13에서 실행
└─ FastAPI Socket.IO 클라이언트로 전송
    │
    │ Socket.IO: wakeword_detected
    ▼
[FastAPI 서버 (socket_handler.py)]
├─ handle_wakeword_detected() 호출
├─ 디바이스 확인 (raspi인지 확인)
└─ 모바일로 이벤트 브로드캐스트
    │
    │ Socket.IO: wakeword_detected
    ▼
[모바일 앱 (MainActivitySttServer.kt)]
├─ handleWakewordDetected() 호출
├─ assets 폴더에서 음성 파일 로드
│   └─ 파일: "001_onAir_서비스를_시작합니다_어떤_것을_도와드릴까요.mp3"
├─ MediaPlayerController.playLocalAudio() 실행
└─ 재생 완료 후 콜백 실행
    │
    │ Socket.IO: wakeword_audio_completed
    ▼
[FastAPI 서버]
├─ handle_wakeword_audio_completed() 호출
└─ 라즈베리파이로 이벤트 전송
    │
    │ Socket.IO: wakeword_audio_completed
    ▼
[브리지 클라이언트]
├─ wakeword_audio_completed 이벤트 수신
└─ 브리지 서버로 전달
    │
    │ Socket.IO: wakeword_audio_completed
    ▼
[브리지 서버]
├─ Python 3.13 → Python 3.10으로 이벤트 전달
└─ 콜백 함수 호출
    │
    ▼
[라즈베리파이 Python 3.10]
├─ wakeword_audio_completed 콜백 실행
└─ 버퍼링 STT 세션 시작 준비
```

#### **단계 3: 버퍼링 STT 세션 시작**
```
[라즈베리파이 Python 3.10]
├─ 버퍼링 STT 세션 시작
├─ 4초간 음성 수집 (settings.STT_BUFFER_DURATION_SEC)
├─ GCP Speech-to-Text API 호출
└─ STT 결과 수신
    │
    │ Socket.IO: stt_result
    │ 데이터: {
    │   "type": "final",
    │   "text": "사용자 음성 텍스트",
    │   "confidence": 0.95
    │ }
    ▼
[브리지 서버]
├─ STT 결과 수신
└─ 브리지 클라이언트로 전달
    │
    │ Socket.IO: stt_result
    ▼
[브리지 클라이언트]
├─ STT 결과 수신
└─ FastAPI Socket.IO 클라이언트로 전송
    │
    │ Socket.IO: stt_result
    ▼
[FastAPI 서버 (socket_handler.py)]
├─ handle_stt_result() 호출
├─ STT 타입 확인 (type="final"이고 session_id 없음 → 버퍼링 STT)
├─ 모바일로 SSE 연결 시작 요청 전송
│   └─ 이벤트: start_sse_connection
└─ Gemini-Flash로 Intent 분류
    │
    │ 함수: classify_intent(stt_text)
    ▼
[FastAPI 서버 - Intent 분류]
├─ Gemini-Flash API 호출
├─ Intent 분류 결과 수신
│   └─ 예: {"intent": "AI_SUPPORTER", "confidence": 0.95}
└─ 모바일로 Intent 결과 전송
    │
    │ Socket.IO: intent_result
    │ 데이터: {
    │   "text": "사용자 음성 텍스트",
    │   "intent": "AI_SUPPORTER" | "OPERATOR",
    │   "confidence": 0.95,
    │   "reasoning": "분류 이유",
    │   "stt_confidence": 0.95
    │ }
    ▼
[모바일 앱]
├─ handleIntentResult() 호출
└─ Intent 타입에 따라 분기 처리
```

---

## 🤖 AI_SUPPORTER 분기

### 단계별 상세 흐름

#### **단계 4: Intent 결과 수신 및 음성 파일 재생**
```
[모바일 앱]
├─ IntentType.AI_SUPPORTER 분기
├─ UI 업데이트: "AI Supporter on" (1초간)
├─ 1초 후 UI 업데이트: "오류 탐지 중..."
└─ 음성 파일 재생
    │
    │ 파일: "001_AI_Supporter_기능을_시작합니다_오류_탐지.mp3"
    │ MediaPlayerController.playLocalAudio()
    │
    └─ 재생 완료 후
        │
        │ Socket.IO: intent_audio_completed
        │ 데이터: {"intent": "AI_SUPPORTER"}
        ▼
[FastAPI 서버]
├─ handle_intent_audio_completed() 호출
└─ AI_SUPPORTER인 경우 CV 모델 실행
```

#### **단계 5: CV 모델 실행**
```
[FastAPI 서버]
├─ Redis에서 최근 프레임 가져오기 (최대 20프레임)
├─ CV 모델 파이프라인 실행
│   ├─ 장비 타입 탐지
│   ├─ 모듈 탐지
│   └─ 이상 탐지
└─ CV 결과 확인
    │
    ├─ [경로 A] CV 탐지 실패
    │   │
    │   └─ 모바일로 cv_detection_failed 전송
    │       │
    │       │ Socket.IO: cv_detection_failed
    │       │ 데이터: {
    │       │   "message": "오류를 탐지하지 못했습니다..."
    │       │ }
    │       ▼
    │   [모바일 앱]
    │   ├─ handleCvDetectionFailed() 호출
    │   ├─ UI 업데이트: CV 탐지 실패 메시지
    │   └─ 음성 파일 재생
    │       │
    │       │ 파일: "001_오류를_탐지하지_못했습니다_AI_Supporter와의.mp3"
    │       │
    │       └─ 재생 완료 후
    │           │
    │           │ Socket.IO: audio_playback_completed
    │           │ 데이터: {
    │           │   "type": "cv_detection_failed"
    │           │ }
    │           ▼
    │       [FastAPI 서버]
    │       ├─ handle_audio_playback_completed() 호출
    │       └─ 라즈베리파이로 Streaming STT 시작 신호 전송
    │           │
    │           │ Socket.IO: start_streaming_stt
    │           │ 데이터: {
    │           │   "session_id": "uuid",
    │           │   "message": "Streaming STT 세션을 시작하세요"
    │           │ }
    │           ▼
    │       [라즈베리파이]
    │       └─ Streaming STT 세션 시작
    │           │
    │           └─ [Clarify Q&A 흐름으로 이동]
    │
    └─ [경로 B] CV 탐지 성공
        │
        ├─ CV 결과 기반 RAG 쿼리 생성
        ├─ RAG 검색 (Hybrid Retrieve + Rerank)
        ├─ GPT-4o로 최종 답변 생성
        ├─ TTS 변환
        └─ 모바일로 최종 답변 전송
            │
            │ Socket.IO: final_answer
            │ 데이터: {
            │   "session_id": null,
            │   "turn_id": 1,
            │   "status": "completed",
            │   "answer": "최종 답변 텍스트",
            │   "structured_answer": {...},
            │   "audio_content": "base64_encoded_audio",
            │   "audio_encoding": "audio/mpeg",
            │   "citations": [...],
            │   "cv_detection_result": {...}
            │ }
            ▼
        [모바일 앱]
        ├─ handleFinalAnswerFromSocket() 호출
        ├─ UI 업데이트: 최종 답변 표시
        └─ TTS 재생
            │
            │ MediaPlayerController.playBase64Audio()
            │
            └─ 재생 완료
```

---

## 📞 OPERATOR 분기

### 단계별 상세 흐름

#### **단계 4: Intent 결과 수신 및 음성 파일 재생**
```
[모바일 앱]
├─ IntentType.OPERATOR 분기
├─ UI 업데이트: "통신 중..."
└─ 음성 파일 재생
    │
    │ 파일: "001_통신_연결을_시작합니다.mp3"
    │ MediaPlayerController.playLocalAudio()
    │
    └─ 재생 완료 후
        │
        │ Socket.IO: intent_audio_completed
        │ 데이터: {"intent": "OPERATOR"}
        ▼
[FastAPI 서버]
├─ handle_intent_audio_completed() 호출
└─ OPERATOR인 경우 CV 로직 실행 안 함
    │
    └─ 모바일에서 WebRTC 연결 요청 처리
        │
        │ HTTP: POST /api/webrtc/request
        │
        └─ WebRTC 연결 시작
```

---

## 💬 CV 탐지 실패 시 Clarify Q&A 흐름

### 단계별 상세 흐름

#### **단계 1: Streaming STT 세션 시작**
```
[라즈베리파이 Python 3.10]
├─ start_streaming_stt 이벤트 수신
├─ Streaming STT 세션 시작
├─ 마이크 ON
└─ 실시간 음성 인식 시작
    │
    │ 사용자 침묵 감지 (0.5초)
    │
    └─ STT 결과 전송
        │
        │ Socket.IO: stt_result
        │ 데이터: {
        │   "type": "final",
        │   "text": "사용자 질문",
        │   "session_id": "uuid",
        │   "confidence": 0.95
        │ }
        ▼
[FastAPI 서버]
├─ handle_stt_result() 호출
├─ session_id 확인 (있음 → Streaming STT)
├─ Redis 세션에 STT 결과 저장
└─ process_clarify_qa_turn() 호출
```

#### **단계 2: Clarify Q&A 턴 처리**
```
[FastAPI 서버]
├─ process_clarify_qa_turn() 실행
├─ 작업자 질문 + LLM 답변 생성
│   ├─ RED/YELLOW: Gemini-Flash Clarify 질문 + LLM 답변
│   └─ GREEN: GPT-4o 최종 답변
├─ TTS 변환
└─ 모바일로 Clarify Q&A 턴 전송
    │
    │ Socket.IO: clarify_qa_turn
    │ 데이터: {
    │   "session_id": "uuid",
    │   "turn_id": 1,
    │   "status": "success",
    │   "user_question": "사용자 질문",
    │   "llm_answer": "LLM 답변",
    │   "need_clarify": true/false,
    │   "audio_content": "base64_encoded_audio",
    │   "audio_encoding": "audio/mpeg"
    │ }
    ▼
[모바일 앱]
├─ handleClarifyQaTurn() 호출
├─ UI 업데이트: 작업자 질문 + LLM 답변 표시
└─ TTS 재생
    │
    │ MediaPlayerController.playBase64Audio()
    │
    └─ 재생 완료 후
        │
        │ Socket.IO: audio_playback_completed
        │ 데이터: {
        │   "type": "clarify_qa_turn",
        │   "session_id": "uuid",
        │   "turn_id": 1
        │ }
        ▼
[FastAPI 서버]
├─ handle_audio_playback_completed() 호출
└─ 다음 Streaming STT 질문 대기
    │
    └─ [단계 1로 반복 또는 최종 답변]
```

#### **단계 3: 최종 답변 (need_clarify=false)**
```
[FastAPI 서버]
├─ need_clarify=false 확인
├─ GPT-4o 최종 답변 생성
├─ TTS 변환
└─ 모바일로 최종 답변 전송
    │
    │ Socket.IO: final_answer
    │ 데이터: {
    │   "session_id": "uuid",
    │   "turn_id": N,
    │   "status": "completed",
    │   "answer": "최종 답변",
    │   "structured_answer": {...},
    │   "audio_content": "base64_encoded_audio",
    │   "audio_encoding": "audio/mpeg"
    │ }
    ▼
[모바일 앱]
├─ handleFinalAnswerFromSocket() 호출
├─ UI 업데이트: 최종 답변 표시
└─ TTS 재생
```

---

## ✅ CV 탐지 성공 시 최종 답변 흐름

### 단계별 상세 흐름

```
[FastAPI 서버]
├─ CV 탐지 성공 확인
├─ CV 결과 기반 RAG 쿼리 생성
│   └─ 예: "밸브에서 이상이 탐지되었습니다"
├─ RAG 검색
│   ├─ Hybrid Retrieve (벡터 검색 + 키워드 검색)
│   └─ Rerank (상위 문서 선별)
├─ GPT-4o로 최종 답변 생성
│   ├─ RAG 문서 기반 답변 생성
│   └─ 구조화된 답변 생성 (summary, tts_text, citations)
├─ TTS 변환
└─ 모바일로 최종 답변 전송
    │
    │ Socket.IO: final_answer
    │ 데이터: {
    │   "session_id": null,
    │   "turn_id": 1,
    │   "status": "completed",
    │   "answer": "최종 답변 텍스트",
    │   "structured_answer": {
    │     "summary": "요약",
    │     "tts_text": "TTS용 텍스트",
    │     "citations": [...]
    │   },
    │   "audio_content": "base64_encoded_audio",
    │   "audio_encoding": "audio/mpeg",
    │   "citations": [...],
    │   "cv_detection_result": {
    │     "device_type": "밸브",
    │     "modules": [...],
    │     "anomalies": {...},
    │     "message": "CV 탐지 메시지"
    │   }
    │ }
    ▼
[모바일 앱]
├─ handleFinalAnswerFromSocket() 호출
├─ UI 업데이트: 최종 답변 표시
└─ TTS 재생
    │
    │ MediaPlayerController.playBase64Audio()
    │
    └─ 재생 완료
```

---

## 📡 이벤트 목록 및 데이터 구조

### 라즈베리파이 → FastAPI

#### 1. `wakeword_detected`
```json
{}
```
- **발신자**: 라즈베리파이 (Python 3.10)
- **경로**: 라즈베리파이 → 브리지 서버 → 브리지 클라이언트 → FastAPI
- **목적**: Wakeword 감지 알림

#### 2. `stt_result`
```json
{
  "type": "final" | "interim" | "error",
  "text": "인식된 텍스트",
  "confidence": 0.95,
  "session_id": "uuid" // Streaming STT인 경우만
}
```
- **발신자**: 라즈베리파이
- **경로**: 라즈베리파이 → 브리지 서버 → 브리지 클라이언트 → FastAPI
- **목적**: STT 결과 전송

### FastAPI → 모바일

#### 3. `wakeword_detected`
```json
{
  "timestamp": null
}
```
- **발신자**: FastAPI
- **목적**: 모바일에서 음성 파일 재생 시작

#### 4. `intent_result`
```json
{
  "text": "사용자 음성 텍스트",
  "intent": "AI_SUPPORTER" | "OPERATOR",
  "confidence": 0.95,
  "reasoning": "분류 이유",
  "stt_confidence": 0.95
}
```
- **발신자**: FastAPI
- **목적**: Intent 분류 결과 전송

#### 5. `cv_detection_failed`
```json
{
  "message": "오류를 탐지하지 못했습니다..."
}
```
- **발신자**: FastAPI
- **목적**: CV 탐지 실패 알림

#### 6. `start_streaming_stt`
```json
{
  "session_id": "uuid",
  "message": "Streaming STT 세션을 시작하세요"
}
```
- **발신자**: FastAPI
- **목적**: 라즈베리파이에 Streaming STT 시작 신호

#### 7. `clarify_qa_turn`
```json
{
  "session_id": "uuid",
  "turn_id": 1,
  "status": "success",
  "user_question": "사용자 질문",
  "llm_answer": "LLM 답변",
  "need_clarify": true,
  "audio_content": "base64_encoded_audio",
  "audio_encoding": "audio/mpeg"
}
```
- **발신자**: FastAPI
- **목적**: Clarify Q&A 턴 전송

#### 8. `final_answer`
```json
{
  "session_id": "uuid" | null,
  "turn_id": 1,
  "status": "completed",
  "answer": "최종 답변 텍스트",
  "structured_answer": {
    "summary": "요약",
    "tts_text": "TTS용 텍스트",
    "citations": [...]
  },
  "audio_content": "base64_encoded_audio",
  "audio_encoding": "audio/mpeg",
  "citations": [...],
  "cv_detection_result": {...} // CV 탐지 성공인 경우만
}
```
- **발신자**: FastAPI
- **목적**: 최종 답변 전송

### 모바일 → FastAPI

#### 9. `wakeword_audio_completed`
```json
{
  "timestamp": 1234567890
}
```
- **발신자**: 모바일
- **목적**: Wakeword 음성 파일 재생 완료 알림

#### 10. `intent_audio_completed`
```json
{
  "intent": "AI_SUPPORTER" | "OPERATOR",
  "timestamp": 1234567890
}
```
- **발신자**: 모바일
- **목적**: Intent 음성 파일 재생 완료 알림

#### 11. `audio_playback_completed`
```json
{
  "type": "cv_detection_failed" | "clarify_qa_turn",
  "session_id": "uuid", // clarify_qa_turn인 경우만
  "turn_id": 1 // clarify_qa_turn인 경우만
}
```
- **발신자**: 모바일
- **목적**: 오디오 재생 완료 알림

### FastAPI → 라즈베리파이

#### 12. `wakeword_audio_completed`
```json
{
  "timestamp": null
}
```
- **발신자**: FastAPI
- **경로**: FastAPI → 브리지 클라이언트 → 브리지 서버 → 라즈베리파이
- **목적**: 모바일 음성 파일 재생 완료 알림

#### 13. `cv_detection_failed`
```json
{
  "message": "오류를 탐지하지 못했습니다..."
}
```
- **발신자**: FastAPI
- **경로**: FastAPI → 브리지 클라이언트 → 브리지 서버 → 라즈베리파이
- **목적**: CV 탐지 실패 알림

---

## 🎵 모바일 오디오 파일 재생 시점

### 1. Wakeword 감지 시
- **파일**: `001_onAir_서비스를_시작합니다_어떤_것을_도와드릴까요.mp3`
- **이벤트**: `wakeword_detected` 수신 시
- **위치**: `MainActivitySttServer.handleWakewordDetected()`

### 2. AI_SUPPORTER Intent 수신 시
- **파일**: `001_AI_Supporter_기능을_시작합니다_오류_탐지.mp3`
- **이벤트**: `intent_result` 수신 시 (intent="AI_SUPPORTER")
- **위치**: `MainActivitySttServer.handleIntentResult()`

### 3. OPERATOR Intent 수신 시
- **파일**: `001_통신_연결을_시작합니다.mp3`
- **이벤트**: `intent_result` 수신 시 (intent="OPERATOR")
- **위치**: `MainActivitySttServer.handleIntentResult()`

### 4. CV 탐지 실패 시
- **파일**: `001_오류를_탐지하지_못했습니다_AI_Supporter와의.mp3`
- **이벤트**: `cv_detection_failed` 수신 시
- **위치**: `MainActivitySttServer.handleCvDetectionFailed()`

### 5. Clarify Q&A 턴 TTS 재생
- **소스**: Base64 인코딩된 오디오 (서버에서 생성)
- **이벤트**: `clarify_qa_turn` 수신 시
- **위치**: `MainActivitySttServer.handleClarifyQaTurn()`

### 6. 최종 답변 TTS 재생
- **소스**: Base64 인코딩된 오디오 (서버에서 생성)
- **이벤트**: `final_answer` 수신 시
- **위치**: `MainActivitySttServer.handleFinalAnswerFromSocket()`

---

## 🔍 디버깅 팁

### Socket.IO 연결 확인
- **라즈베리파이**: `SocketIOClient.is_connected()` 확인
- **모바일**: `SocketIoSttClient.isConnected()` 확인
- **FastAPI**: `device_map` 확인

### 이벤트 수신 확인
- **라즈베리파이**: 로그에서 `📩 [단계 X]` 확인
- **FastAPI**: 로그에서 `📝 [단계 X]` 확인
- **모바일**: Logcat에서 `📩` 또는 `🔔` 로그 확인

### 오디오 재생 확인
- **모바일**: Logcat에서 `🎵`, `🔊`, `▶️` 로그 확인
- **파일 존재**: `📂 Assets 폴더 파일 목록` 로그 확인
- **재생 상태**: `MediaPlayer 상태: isPlaying=...` 로그 확인

---

## 📝 주요 파일 위치

### 라즈베리파이
- `ai_raspi/AI_Supporter/main_py310.py`: 메인 STT 루프
- `ai_raspi/AI_Supporter/bridge/stt_bridge_server.py`: 브리지 서버
- `ai_raspi/AI_Supporter/bridge/stt_bridge_client.py`: 브리지 클라이언트
- `ai_raspi/AI_Supporter/stt/socketio_client.py`: Socket.IO 클라이언트

### FastAPI 서버
- `ai_server/rag_server/app/sockets/socket_handler.py`: Socket.IO 핸들러
- `ai_server/rag_server/app/services/intent_service.py`: Intent 분류
- `ai_server/rag_server/app/services/cv_service.py`: CV 모델 실행
- `ai_server/rag_server/app/services/rag_service.py`: RAG 검색

### 모바일 앱
- `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt`: 메인 Activity
- `mobile/app/src/main/java/com/onair/mobile/assistant/data/stt/SocketIoSttClient.kt`: Socket.IO 클라이언트
- `mobile/app/src/main/java/com/onair/mobile/assistant/data/tts/MediaPlayerController.kt`: 오디오 재생 컨트롤러

---

## ⚠️ 주의사항

1. **브리지 서버 연결**: Python 3.10과 Python 3.13 간 통신을 위해 브리지 서버가 반드시 실행되어야 함
2. **디바이스 등록**: Socket.IO 연결 시 `register_device` 이벤트로 디바이스 타입 등록 필수
3. **세션 ID**: Streaming STT는 `session_id`가 있어야 Clarify Q&A로 처리됨
4. **오디오 파일**: assets 폴더의 파일명이 정확해야 함 (한글 파일명 주의)
5. **타임아웃**: 모바일 음성 파일 재생 완료 대기 시간은 최대 30초

