# 💬 AI_Supporter Clarify 대화 턴 처리 흐름

## 📋 개요

AI_Supporter 기능에서 Clarify를 위한 대화 턴은 **라즈베리파이 → FastAPI → 모바일** 간에 다음과 같이 주고받습니다:

1. **라즈베리파이**: Streaming STT로 사용자 음성 입력을 실시간 인식
2. **FastAPI**: STT 결과를 받아 RAG 검색, Evidence Check, Clarify 질문/답변 생성
3. **모바일**: Clarify 질문/답변을 TTS로 재생
4. **라즈베리파이**: TTS 재생 완료 후 다시 사용자 음성 입력 대기 (Streaming STT 계속 실행)

---

## 🔄 전체 흐름도

```
[사용자 음성 입력]
        │
        ▼
[라즈베리파이 Python 3.10]
├─ Streaming STT 실행 중 (계속 실행)
├─ 사용자 침묵 감지 (0.5초)
└─ STT 결과 전송
    │
    │ Socket.IO: stt_result
    │ {
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
    │
    ├─ [1] 히스토리 컨텍스트 구성
    ├─ [2] Hybrid Search + Rerank (RAG)
    ├─ [3] Evidence Check (RED/YELLOW/GREEN)
    │
    ├─ [경로 A] RED/YELLOW (need_clarify=True)
    │   ├─ [4] Clarify 질문 생성 (Gemini-Flash)
    │   ├─ [5] LLM 답변 생성 (Gemini-Flash)
    │   ├─ [6] TTS 변환
    │   └─ [7] 모바일로 clarify_qa_turn 이벤트 전송
    │       │
    │       │ Socket.IO: clarify_qa_turn
    │       │ {
    │       │   "session_id": "uuid",
    │       │   "turn_id": 1,
    │       │   "user_question": "사용자 질문",
    │       │   "llm_answer": "LLM 답변",
    │       │   "audio_content": "base64_encoded_audio",
    │       │   "audio_encoding": "audio/mpeg",
    │       │   "need_clarify": true,
    │       │   "gate_decision": "RED" | "YELLOW",
    │       │   "status": "success"
    │       │ }
    │       ▼
    │   [모바일 앱]
    │   ├─ handleClarifyQaTurn() 호출
    │   ├─ UI 업데이트: 작업자 질문 + LLM 답변 표시
    │   └─ TTS 재생 (MediaPlayerController.playAudio())
    │       │
    │       │ 재생 완료 후
    │       │
    │       │ Socket.IO: audio_playback_completed
    │       │ {
    │       │   "type": "clarify_qa_turn",
    │       │   "session_id": "uuid",
    │       │   "turn_id": 1
    │       │ }
    │       ▼
    │   [FastAPI 서버]
    │   ├─ handle_audio_playback_completed() 호출
    │   └─ 다음 Streaming STT 질문 대기 (별도 처리 없음)
    │       │
    │       ▼
    │   [라즈베리파이]
    │   └─ Streaming STT가 계속 실행 중
    │       └─ 사용자의 다음 질문을 대기
    │           │
    │           └─ [다시 처음으로] 사용자 음성 입력 대기
    │
    └─ [경로 B] GREEN (need_clarify=False)
        ├─ [8] 최종 답변 생성 (GPT-4o)
        ├─ [9] TTS 변환
        └─ [10] 모바일로 final_answer 이벤트 전송
            │
            │ Socket.IO: final_answer
            │ {
            │   "session_id": "uuid",
            │   "turn_id": 1,
            │   "status": "completed",
            │   "answer": "최종 답변",
            │   "audio_content": "base64_encoded_audio",
            │   "audio_encoding": "audio/mpeg",
            │   "structured_answer": {...},
            │   "citations": [...]
            │ }
            ▼
        [모바일 앱]
        ├─ handleFinalAnswerFromSocket() 호출
        ├─ UI 업데이트: 최종 답변 표시
        └─ TTS 재생
            │
            │ 재생 완료 후
            │
            │ Socket.IO: audio_playback_completed
            │ {
            │   "type": "final_answer",
            │   "session_id": "uuid",
            │   "turn_id": 1
            │ }
            ▼
        [FastAPI 서버]
        ├─ handle_audio_playback_completed() 호출
        └─ [11] 라즈베리파이로 service_completed 이벤트 전송
            │
            │ Socket.IO: service_completed
            │ {
            │   "session_id": "uuid",
            │   "status": "completed"
            │ }
            ▼
        [라즈베리파이]
        └─ Streaming STT 종료 + Wakeword 재활성화
```

---

## 📝 단계별 상세 설명

### 1단계: 라즈베리파이 Streaming STT 시작

**파일**: `ai_raspi/AI_Supporter/stt/gcp_stt_stream.py`

```python
# CV 탐지 실패 시 FastAPI에서 start_streaming_stt 이벤트 수신
@sio.on("start_streaming_stt")
async def handle_start_streaming_stt(data):
    session_id = data.get("session_id")
    # Streaming STT 시작
    await streaming_stt.run(mic, session_id=session_id)
```

**특징**:
- Streaming STT는 **계속 실행**됨 (사용자가 질문할 때까지 대기)
- 침묵 감지 (0.5초) 후 `final` 결과 전송
- `session_id`를 포함하여 FastAPI로 전송

---

### 2단계: FastAPI STT 결과 수신 및 처리

**파일**: `ai_server/rag_server/app/sockets/socket_handler.py`

```python
async def handle_stt_result(sid, data):
    # session_id가 있으면 Streaming STT
    if session_id:
        # Redis 세션에 STT 텍스트 저장
        memory.append_event(session_id, {
            "role": "user",
            "type": "streaming_stt",
            "data": {"text": stt_text, "type": stt_type}
        })
        
        # type="final"이면 Clarify 처리
        if stt_type == "final":
            await process_clarify_qa_turn(session_id, stt_text)
```

---

### 3단계: Clarify Q&A 턴 처리

**파일**: `ai_server/rag_server/app/sockets/socket_handler.py`

**함수**: `process_clarify_qa_turn(session_id, user_question)`

#### 3-1. 히스토리 컨텍스트 구성
```python
# 이전 대화 기록 반영 (최근 2개 질문)
history = memory.get_history(session_id)
effective_query = f"{history_context} \n{user_question}"
```

#### 3-2. Hybrid Search + Rerank
```python
base_hits = hybrid_retrieve(normalized_query, top_k=8)
hits = rerank(normalized_query, base_hits, top_k=6)
used_hits = hits[:5]
```

#### 3-3. Evidence Check (RED/YELLOW/GREEN)
```python
need_clarify, evidence_stats = comprehensive_evidence_check(effective_query, used_hits)
gate_decision = evidence_stats.get("gate_decision")  # "RED" | "YELLOW" | "GREEN"
```

#### 3-4. RED/YELLOW 경로: Clarify 질문/답변 생성

```python
if need_clarify or gate_decision != "GREEN":
    # [4] Clarify 질문 생성 (Gemini-Flash)
    clarified_result = make_clarify_prompt(effective_query, used_hits, evidence_stats)
    clarify_question = clarified_result.get("guide", "...")
    
    # [5] LLM 답변 생성 (Gemini-Flash)
    model_qa = genai.GenerativeModel("gemini-1.5-flash")
    qa_response = model_qa.generate_content(qa_prompt)
    llm_answer = qa_response.text.strip()
    
    # [6] TTS 변환
    tts_result = text_to_speech(llm_answer)
    audio_content = tts_result.get("audio_content")
    
    # [7] 모바일로 clarify_qa_turn 이벤트 전송
    await broadcast_to("mobile", "clarify_qa_turn", {
        "session_id": session_id,
        "turn_id": turn_id,
        "user_question": user_question,
        "llm_answer": llm_answer,
        "audio_content": audio_content,
        "audio_encoding": "audio/mpeg",
        "need_clarify": True,
        "gate_decision": gate_decision,
        "status": "success"
    })
```

#### 3-5. GREEN 경로: 최종 답변 생성

```python
else:
    # [8] 최종 답변 생성 (GPT-4o)
    answer_result = llm_generate_answer(effective_query, snippets, used_hits)
    answer_text = answer_result.get("tts_text")
    
    # [9] TTS 변환
    tts_result = text_to_speech(answer_text)
    
    # [10] 모바일로 final_answer 이벤트 전송
    await broadcast_to("mobile", "final_answer", {
        "session_id": session_id,
        "turn_id": turn_id,
        "status": "completed",
        "answer": answer_text,
        "audio_content": audio_content,
        "structured_answer": structured_answer,
        "citations": [...]
    })
    
    # [11] 라즈베리파이로 service_completed 이벤트 전송
    await broadcast_to("raspi", "service_completed", {
        "session_id": session_id,
        "status": "completed"
    })
```

---

### 4단계: 모바일 Clarify Q&A 턴 수신 및 처리

**파일**: `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt`

```kotlin
private fun handleClarifyQaTurn(qaTurn: ClarifyQaTurnDto) {
    // UI 업데이트: 작업자 질문 + LLM 답변 표시
    clarifyText.text = "Clarify: Q) ${qaTurn.user_question}\nA) ${qaTurn.llm_answer}"
    
    // TTS 재생
    if (qaTurn.audio_content != null) {
        ttsRepository.playAudio(qaTurn.audio_content, qaTurn.audio_encoding) {
            // 재생 완료 후 이벤트 전송
            socketIoSttClient.sendClarifyQaTurnAudioCompleted(
                qaTurn.session_id ?: "",
                qaTurn.turn_id ?: 1
            )
        }
    }
}
```

**이벤트 전송**:
```kotlin
// Socket.IO: audio_playback_completed
socket?.emit("audio_playback_completed", {
    "type": "clarify_qa_turn",
    "session_id": sessionId,
    "turn_id": turnId
})
```

---

### 5단계: FastAPI 재생 완료 수신

**파일**: `ai_server/rag_server/app/sockets/socket_handler.py`

```python
async def handle_audio_playback_completed(sid, data):
    audio_type = data.get("type")
    
    if audio_type == "clarify_qa_turn":
        # Clarify Q&A 턴 TTS 재생 완료
        # 별도 처리 없음 - 라즈베리파이 Streaming STT가 계속 실행 중
        print("✅ Clarify Q&A 턴 TTS 재생 완료")
        print("   다음 Streaming STT 질문을 대기 중입니다.")
```

**중요**: FastAPI는 별도 처리를 하지 않습니다. 라즈베리파이의 Streaming STT가 계속 실행 중이므로 사용자의 다음 질문을 자동으로 받습니다.

---

### 6단계: 라즈베리파이 Streaming STT 계속 실행

**파일**: `ai_raspi/AI_Supporter/stt/gcp_stt_stream.py`

```python
# Streaming STT는 계속 실행 중
# 사용자가 다음 질문을 말하면:
# 1. 침묵 감지 (0.5초)
# 2. final 결과 전송
# 3. FastAPI로 다시 전송
# 4. process_clarify_qa_turn() 다시 호출
```

**특징**:
- Streaming STT는 **서비스 종료 신호(`service_completed`)를 받을 때까지 계속 실행**
- 사용자가 질문할 때마다 자동으로 FastAPI로 전송
- Clarify 루프가 반복됨 (RED/YELLOW → GREEN까지)

---

## 🔑 핵심 포인트

### 1. **Streaming STT는 계속 실행됨**
- Clarify 루프 중에도 라즈베리파이의 Streaming STT는 계속 실행
- 사용자가 질문할 때마다 자동으로 FastAPI로 전송
- 별도의 "다음 질문 시작" 이벤트가 필요 없음

### 2. **모바일은 수신만 함**
- 모바일은 `clarify_qa_turn` 이벤트를 수신하여 TTS 재생
- TTS 재생 완료 후 `audio_playback_completed` 이벤트만 전송
- **모바일에서 별도로 텍스트 입력을 보내지 않음**

### 3. **Clarify 루프 반복**
- RED/YELLOW: Clarify 질문/답변 생성 → 모바일 TTS 재생 → 다음 질문 대기
- GREEN: 최종 답변 생성 → 모바일 TTS 재생 → 서비스 종료

### 4. **히스토리 관리**
- Redis에 모든 대화 기록 저장 (`memory.append_event()`)
- 이전 질문과 Clarify 질문을 포함하여 컨텍스트 구성
- 최근 2개 질문을 결합하여 검색

---

## 📊 이벤트 흐름 요약

| 단계 | 발신자 | 수신자 | 이벤트 | 데이터 |
|------|--------|--------|--------|--------|
| 1 | 라즈베리파이 | FastAPI | `stt_result` | `{type: "final", text: "...", session_id: "..."}` |
| 2 | FastAPI | 모바일 | `clarify_qa_turn` | `{session_id, turn_id, user_question, llm_answer, audio_content, need_clarify: true}` |
| 3 | 모바일 | FastAPI | `audio_playback_completed` | `{type: "clarify_qa_turn", session_id, turn_id}` |
| 4 | 라즈베리파이 | FastAPI | `stt_result` | `{type: "final", text: "다음 질문", session_id: "..."}` (반복) |
| 5 | FastAPI | 모바일 | `final_answer` | `{session_id, turn_id, answer, audio_content, status: "completed"}` (GREEN 시) |
| 6 | FastAPI | 라즈베리파이 | `service_completed` | `{session_id, status: "completed"}` (GREEN 시) |

---

## 🔍 주요 코드 위치

### 라즈베리파이
- **Streaming STT 시작**: `ai_raspi/AI_Supporter/stt/socketio_client.py` - `handle_start_streaming_stt()`
- **STT 결과 전송**: `ai_raspi/AI_Supporter/stt/gcp_stt_stream.py` - `run()`
- **서비스 종료 처리**: `ai_raspi/AI_Supporter/stt/socketio_client.py` - `handle_service_completed()`

### FastAPI
- **STT 결과 수신**: `ai_server/rag_server/app/sockets/socket_handler.py` - `handle_stt_result()`
- **Clarify 처리**: `ai_server/rag_server/app/sockets/socket_handler.py` - `process_clarify_qa_turn()`
- **재생 완료 수신**: `ai_server/rag_server/app/sockets/socket_handler.py` - `handle_audio_playback_completed()`

### 모바일
- **Clarify Q&A 턴 수신**: `mobile/app/src/main/java/com/onair/mobile/MainActivitySttServer.kt` - `handleClarifyQaTurn()`
- **재생 완료 전송**: `mobile/app/src/main/java/com/onair/mobile/assistant/data/stt/SocketIoSttClient.kt` - `sendClarifyQaTurnAudioCompleted()`

---

## ⚠️ 주의사항

1. **Streaming STT 세션 관리**
   - `session_id`는 Clarify 세션 전체에서 유지되어야 함
   - Redis에 히스토리가 저장되므로 세션 ID가 일치해야 함

2. **침묵 감지**
   - 라즈베리파이에서 0.5초 침묵 감지 후 `final` 결과 전송
   - 너무 짧으면 불완전한 문장이 전송될 수 있음

3. **TTS 재생 완료 대기**
   - 모바일에서 TTS 재생이 완료되어야 다음 질문을 받을 수 있음
   - `audio_playback_completed` 이벤트는 필수

4. **서비스 종료**
   - GREEN 경로에서만 `service_completed` 이벤트 전송
   - 라즈베리파이에서 Streaming STT 종료 및 Wakeword 재활성화

