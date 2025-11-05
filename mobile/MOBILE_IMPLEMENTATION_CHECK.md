# 모바일 단 구현 상태 점검 결과

## ✅ 구현 완료 항목

### 1. STT 텍스트 수신
- ✅ WebSocket 서버 (포트 8080) - 라즈베리파이로부터 버퍼링 STT 텍스트 수신
- ✅ HTTP 웹훅 서버 (포트 8081) - stt_start 알림 수신

### 2. Intent 분류
- ✅ Phi-3 임베딩 추출 API 호출 (`POST /api/embedding`)
- ✅ ONNX Intent Classifier 실행
- ✅ OPERATOR / AI_SUPPORTER 분기

### 3. RAG + LLM 처리
- ✅ RAG Chat API 연동 (`POST /rag/chat`)
- ✅ 세션 관리 (SessionManager)
- ✅ Clarify 처리 로직
- ✅ 최종 답변 처리

### 4. TTS 재생
- ✅ Base64 오디오 디코딩
- ✅ MediaPlayer 재생

---

## ❌ 누락된 항목 (중요!)

### 1. 라즈베리파이 제어 API 호출

**문제점**: 모바일이 라즈베리파이에 제어 시그널을 보내지 않음

**필요 구현**:
- 라즈베리파이 FastAPI 서버 (`http://RASPBERRY_PI_IP:PORT`)에 제어 API 호출
- Intent 분류 후 반드시 호출해야 함:

```
AI_SUPPORTER 분기 시:
1. POST http://라즈베리파이_IP:PORT/api/stt/mode {"mode": "streaming"}
   → 마이크 자동 resume
2. POST http://라즈베리파이_IP:PORT/api/stt/intent_done {"branch": "AI_SUPPORTER"}
   → 상태 동기화 (선택사항)

OPERATOR 분기 시:
1. POST http://라즈베리파이_IP:PORT/api/stt/intent_done {"branch": "OPERATOR"}
   → 마이크 resume + 모드 buffered 유지
```

**현재 상태**: 구현 없음 ⚠️

---

### 2. FastAPI 서버 WebSocket 클라이언트 (`/ws/chat`)

**문제점**: Streaming STT는 FastAPI 서버로 직접 전송됨

**설계 확인 필요**:
- 라즈베리파이: Streaming STT → FastAPI `/ws/chat` 직접 전송
- 모바일: `/ws/chat`에서 Streaming STT를 받아야 하는가?
- 아니면 FastAPI가 중간에서 처리하고 모바일에는 `/rag/chat` 응답만 전달?

**현재 상태**: 불명확 ⚠️

---

## 🔍 설계 불일치 확인 필요

### 1. 버퍼링 STT 결과 수신 경로

**라즈베리파이 코드**:
```python
# broadcast()는 등록된 외부 WebSocket으로 전송
manager.broadcast(message)
```

**질문**:
- 이 "외부 WebSocket"이 모바일의 WebSocket 서버인가?
- 라즈베리파이가 모바일의 `ws://<모바일_IP>:8080/ws/stt`에 연결하는가?

**현재 모바일 구현**: ✅ WebSocket 서버 있음 (포트 8080)

---

### 2. Streaming STT 흐름

**라즈베리파이 코드**:
```python
# Streaming STT는 FastAPI 서버의 /ws/chat으로 직접 전송
ws_client.send_text(text)  # FastAPI 서버로 전송
```

**질문**:
- 모바일은 `/ws/chat`에서 Streaming STT를 받아야 하는가?
- 아니면 FastAPI가 처리하고 모바일에는 `/rag/chat` 응답만 전달?

**현재 모바일 구현**: ❌ `/ws/chat` WebSocket 클라이언트 없음

---

## 📝 추가 구현 필요 항목

### 1. 라즈베리파이 제어 API 클라이언트

**필요 파일**:
- `app/src/main/java/com/onair/mobile/assistant/data/raspberry/RaspberryPiControlApi.kt`
- `app/src/main/java/com/onair/mobile/assistant/data/raspberry/RaspberryPiControlRepository.kt`

**구현 내용**:
```kotlin
interface RaspberryPiControlApi {
    @POST("/api/stt/mode")
    suspend fun setSttMode(@Body request: SttModeRequest): Response
    
    @POST("/api/stt/intent_done")
    suspend fun notifyIntentDone(@Body request: IntentDoneRequest): Response
}

data class SttModeRequest(val mode: String)  // "buffered" or "streaming"
data class IntentDoneRequest(val branch: String)  // "AI_SUPPORTER" or "OPERATOR"
```

**호출 시점**:
- `handleDispatchResult()`에서 Intent 분류 후 즉시 호출

---

### 2. FastAPI 서버 WebSocket 클라이언트 (확인 필요)

**만약 필요하다면**:
- `app/src/main/java/com/onair/mobile/assistant/data/llm/FastApiWebSocketClient.kt`

**구현 내용**:
```kotlin
class FastApiWebSocketClient {
    suspend fun connect(url: String)
    suspend fun sendText(text: String, sessionId: String?)
    suspend fun listenResponses(callback: (RagResponse) -> Unit)
    fun disconnect()
}
```

---

## ⚠️ 핵심 누락 사항

### 1. 라즈베리파이 제어 API 호출 (필수!)

**현재 문제**:
- Intent 분류 후 라즈베리파이에 제어 시그널을 보내지 않음
- 결과: 라즈베리파이 마이크가 OFF 상태로 유지됨
- Streaming STT가 시작되지 않음

**영향**:
- AI_SUPPORTER 분기 후 Clarify 입력을 받을 수 없음
- OPERATOR 분기 후 통신이 시작되지 않음

---

## ✅ 구현 완료 체크리스트

- [x] WebSocket 서버 (라즈베리파이 STT 텍스트 수신)
- [x] HTTP 웹훅 서버 (stt_start 알림)
- [x] Intent 분류 (Phi-3 + ONNX)
- [x] RAG Chat API (`/rag/chat`)
- [x] 세션 관리
- [x] Clarify 처리 로직
- [x] TTS 재생
- [ ] 라즈베리파이 제어 API 호출 ❌ **누락**
- [ ] FastAPI WebSocket 클라이언트 (`/ws/chat`) ❓ **확인 필요**

---

## 🎯 우선 구현 필요

**1순위: 라즈베리파이 제어 API 호출**
- Intent 분류 후 반드시 호출해야 함
- 없으면 마이크가 OFF 상태로 유지되어 Streaming STT 불가능

**2순위: FastAPI WebSocket 클라이언트**
- 설계 확인 필요: 모바일이 직접 받아야 하는지, 아니면 REST API만 사용하는지

