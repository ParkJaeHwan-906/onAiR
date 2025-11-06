# 📱 모바일 프로젝트 구현 로직 전체 정리

## 📋 목차
1. [아키텍처 개요](#아키텍처-개요)
2. [데이터 흐름](#데이터-흐름)
3. [주요 컴포넌트](#주요-컴포넌트)
4. [세부 구현 로직](#세부-구현-로직)
5. [의존성 및 라이브러리](#의존성-및-라이브러리)
6. [미구현 항목](#미구현-항목)

---

## 🏗️ 아키텍처 개요

### 전체 시스템 구조
```
┌─────────────────────────────────────────────────────────────┐
│                    라즈베리파이 제로                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Wakeword    │→ │ STT (GCP)    │→ │ WebSocket/HTTP   │  │
│  │ Detection   │  │              │  │ Client           │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ WebSocket: ws://<Android_IP>:8080/ws/stt
                          │ HTTP: POST http://<Android_IP>:8081/webhook/stt_start
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    안드로이드 모바일 앱                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MainActivitySttServer (Entry Point)                │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │  SttWebSocketServer (포트 8080)              │  │  │
│  │  │  SttWebhookServer (포트 8081)                │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  │                     │                               │  │
│  │                     ▼                               │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │  SttRepositoryImpl                           │  │  │
│  │  │  └─ RaspberryPiTextReceiver                  │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  │                     │                               │  │
│  │                     ▼                               │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │  ClassifyIntentUseCase                       │  │  │
│  │  │  └─ IntentRepositoryImpl                     │  │  │
│  │  │      ├─ EmbeddingRepository (FastAPI 호출)  │  │  │
│  │  │      └─ OnnxIntentClassifierDataSource       │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  │                     │                               │  │
│  │                     ▼                               │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │  DispatchIntentUseCase                      │  │  │
│  │  │  ├─ OPERATOR → RTC Start (TODO)             │  │  │
│  │  │  └─ AI_SUPPORTER → CV → Clarify → RAG+LLM  │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ HTTP: POST http://<FastAPI_IP>:8000/api/embedding
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 서버                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /api/embedding                                       │  │
│  │  Phi-3-mini-4k-instruct 임베딩 추출                  │  │
│  │  응답: {"embedding": [3072차원 FloatArray]}          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Clean Architecture 레이어 구조
```
┌─────────────────────────────────────────────────────────┐
│ UI Layer (Presentation)                                 │
│ - MainActivitySttServer                                  │
│ - AssistantScreen (미사용)                               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Domain Layer                                            │
│ - UseCase (ClassifyIntentUseCase, DispatchIntentUseCase)│
│ - Entity (IntentType, IntentClassificationDto)          │
│ - Repository Interface                                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Data Layer                                              │
│ - Repository Implementation                             │
│ - DataSource (ONNX, Retrofit, WebSocket)                │
│ - DTO (Request/Response)                                │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 데이터 흐름

### 1. STT 텍스트 수신 흐름

```
[라즈베리파이]
1. Wakeword 감지 ("onAir")
   ↓
2. HTTP POST /webhook/stt_start → 안드로이드
   ↓
3. 마이크 활성화 및 음성 수집 (3~5초)
   ↓
4. GCP Speech-to-Text API 호출
   ↓
5. WebSocket으로 텍스트 전송 → 안드로이드
   {
     "timestamp": "1234567890",
     "text": "에러가 발생했어요"
   }

[안드로이드]
6. SttWebhookServer.onSttStart() 호출
   ↓
7. SttWebSocketServer.onMessage() 수신
   ↓
8. JSON 파싱 → SttRepositoryImpl.receiveFromRaspberryPi(text)
   ↓
9. RaspberryPiTextReceiver.receivedText Flow 업데이트
```

### 2. Intent 분류 흐름

```
[안드로이드]
1. MainActivitySttServer.handleSttMessage(text)
   ↓
2. ClassifyIntentUseCase(text)
   ↓
3. IntentRepositoryImpl.classifyIntent(text)
   ↓
4. EmbeddingRepository.extractEmbedding(text)
   ├─ POST http://<FastAPI_IP>:8000/api/embedding
   ├─ Request: {"text": "에러가 발생했어요"}
   └─ Response: {"embedding": [3072차원 FloatArray]}
   ↓
5. OnnxIntentClassifierDataSource.classifyWithEmbedding(embedding)
   ├─ Assets에서 intent_classifier.int8.onnx 로드
   ├─ ONNX Runtime 세션 생성
   ├─ 3072차원 임베딩 → ONNX 모델 입력
   ├─ 추론 실행 (logits 출력)
   └─ 파싱: [0] = AI_SUPPORTER, [1] = OPERATOR
   ↓
6. IntentClassificationDto 반환
   {
     intentType: AI_SUPPORTER,
     confidence: 0.95,
     rawText: "에러가 발생했어요"
   }
```

### 3. Intent 분기 처리 흐름

```
[안드로이드]
1. DispatchIntentUseCase(intentResult)
   ↓
2. intentType 분기
   ├─ OPERATOR → handleOperatorIntent()
   │   └─ TODO: RTC Start 로직 구현
   │
   └─ AI_SUPPORTER → handleAiSupporterIntent()
       ├─ 1) tryExtractErrorFromCv(contextText)
       │   └─ DetectObjectUseCase.detectError() (TODO)
       │
       ├─ 2) CV 실패 시 buildClarifiedQuery(text)
       │   └─ ClarifyQuestionUseCase.clarify() (TODO)
       │
       └─ 3) callRagLlm(queryForRag)
           └─ LlmRepository.generateRagResponse() (TODO)
       ↓
3. DispatchResult 반환
   └─ Success(type, message, data) 또는 Error(message)
```

---

## 🧩 주요 컴포넌트

### 1. Entry Point: MainActivitySttServer

**위치**: `app/src/main/java/com/onair/mobile/MainActivitySttServer.kt`

**역할**:
- 안드로이드 앱의 진입점
- WebSocket 서버 (포트 8080) 및 HTTP 웹훅 서버 (포트 8081) 초기화
- 전체 파이프라인 오케스트레이션

**주요 메서드**:
```kotlin
onCreate()
├─ SttRepositoryImpl 초기화
├─ EmbeddingRepository 초기화 (FastAPI 서버 URL 필요)
├─ IntentRepositoryImpl 초기화
├─ ClassifyIntentUseCase 초기화
├─ DispatchIntentUseCase 초기화
├─ SttWebSocketServer 시작 (포트 8080)
└─ SttWebhookServer 시작 (포트 8081)

handleSttStart()
└─ 라즈베리파이로부터 stt_start 알림 수신 처리

handleSttMessage(timestamp, text)
├─ SttRepository에 텍스트 전달
├─ ClassifyIntentUseCase 호출
├─ DispatchIntentUseCase 호출
└─ 결과 처리 (handleDispatchResult)

onDestroy()
├─ WebSocket 서버 중지
├─ Webhook 서버 중지
└─ 리소스 정리
```

**초기화 시 TODO**:
- FastAPI 서버 URL 설정 (현재: `"http://YOUR_FASTAPI_SERVER_URL:8000"`)
- DetectObjectUseCase 주입 (현재: null)
- ClarifyQuestionUseCase 주입 (현재: null)
- LlmRepository 주입 (현재: null)

---

### 2. STT 수신 계층

#### 2.1. SttWebSocketServer

**위치**: `app/src/main/java/com/onair/mobile/assistant/data/stt/SttWebSocketServer.kt`

**역할**:
- 라즈베리파이로부터 STT 텍스트를 실시간으로 수신하는 WebSocket 서버
- Java-WebSocket 라이브러리 사용

**주요 메서드**:
```kotlin
onOpen(conn, handshake)
└─ 라즈베리파이 연결 성공 로깅

onMessage(conn, message)
├─ JSON 파싱: {"timestamp": "...", "text": "..."}
├─ 빈 텍스트 검증
└─ onSttMessage(timestamp, text) 콜백 호출

onClose(conn, code, reason, remote)
└─ 연결 종료 로깅

onError(conn, ex)
└─ 에러 처리 및 로깅

stopServer()
└─ 서버 중지
```

**메시지 형식**:
```json
{
  "timestamp": "1234567890",
  "text": "에러가 발생했어요"
}
```

---

#### 2.2. SttWebhookServer

**위치**: `app/src/main/java/com/onair/mobile/assistant/data/stt/SttWebhookServer.kt`

**역할**:
- 라즈베리파이로부터 `stt_start` 알림을 수신하는 경량 HTTP 서버
- NanoHTTPD 라이브러리 사용

**주요 메서드**:
```kotlin
serve(session)
├─ POST /webhook/stt_start 엔드포인트 처리
└─ 다른 요청은 404 반환

handleSttStart(session)
├─ POST 본문 읽기
├─ JSON 파싱: {"event": "stt_start"}
├─ 이벤트 검증
└─ onSttStart() 콜백 호출

startServer()
└─ 서버 시작 (포트 8081)

stopServer()
└─ 서버 중지
```

**요청 형식**:
```json
POST /webhook/stt_start
{
  "event": "stt_start"
}
```

**응답 형식**:
```json
{
  "status": "ok",
  "message": "STT start notification received"
}
```

---

#### 2.3. SttRepositoryImpl

**위치**: `app/src/main/java/com/onair/mobile/assistant/data/stt/SttRepositoryImpl.kt`

**역할**:
- 라즈베리파이로부터 받은 텍스트를 관리하는 Repository 구현체
- `SttRepository` 인터페이스 구현

**주요 메서드**:
```kotlin
receiveFromRaspberryPi(text)
└─ RaspberryPiTextReceiver.receiveText(text) 호출

getRaspberryPiTextFlow()
└─ StateFlow<String> 반환 (실시간 텍스트 업데이트)

transcribe(audioBytes)
└─ 미사용 (라즈베리파이 방식에서는 불필요)

cleanup()
└─ RaspberryPiTextReceiver.clear() 호출
```

---

#### 2.4. RaspberryPiTextReceiver

**위치**: `app/src/main/java/com/onair/mobile/assistant/data/stt/RaspberryPiTextReceiver.kt`

**역할**:
- 라즈베리파이로부터 받은 텍스트를 StateFlow로 관리
- 실시간 업데이트를 위한 반응형 스트림 제공

**주요 속성**:
```kotlin
_receivedText: MutableStateFlow<String>
receivedText: StateFlow<String> (public)
```

**주요 메서드**:
```kotlin
receiveText(text)
├─ 빈 텍스트 검증
├─ 로깅
└─ _receivedText.value = text

clear()
└─ _receivedText.value = ""
```

---

### 3. Intent 분류 계층

#### 3.1. ClassifyIntentUseCase

**위치**: `app/src/main/java/com/onair/mobile/assistant/domain/usecase/ClassifyIntentUseCase.kt`

**역할**:
- Intent 분류 UseCase (Domain Layer)
- 단순히 `IntentRepository.classifyIntent()` 위임

**구현**:
```kotlin
suspend operator fun invoke(text: String): IntentClassificationDto {
    return intentRepository.classifyIntent(text)
}
```

---

#### 3.2. IntentRepositoryImpl

**위치**: `app/src/main/java/com/onair/mobile/assistant/data/intent/IntentRepositoryImpl.kt`

**역할**:
- Intent 분류 Repository 구현체
- FastAPI 서버로부터 Phi-3 임베딩을 받아서 ONNX 모델로 분류

**의존성**:
- `EmbeddingRepository` (FastAPI 서버 호출)
- `OnnxIntentClassifierDataSource` (ONNX 모델 실행)

**주요 메서드**:
```kotlin
classifyIntent(text)
├─ EmbeddingRepository.extractEmbedding(text)
│   └─ FastAPI 서버 호출 → 3072차원 FloatArray 수신
├─ OnnxIntentClassifierDataSource.classifyWithEmbedding(embedding)
│   └─ ONNX 모델 추론 → Intent 분류 결과
└─ IntentClassificationDto 반환

cleanup()
└─ OnnxIntentClassifierDataSource.cleanup()
```

---

#### 3.3. EmbeddingRepository

**위치**: `app/src/main/java/com/onair/mobile/assistant/data/intent/EmbeddingRepository.kt`

**역할**:
- FastAPI 서버로부터 Phi-3 임베딩을 받아오는 Repository
- Retrofit을 사용한 HTTP 클라이언트

**의존성**:
- `EmbeddingApi` (Retrofit 인터페이스)

**주요 메서드**:
```kotlin
extractEmbedding(text)
├─ EmbeddingRequest 생성: {"text": text}
├─ EmbeddingApi.extractEmbedding(request) 호출
├─ EmbeddingResponse 수신: {"embedding": [List<Float>]}
├─ List<Float> → FloatArray 변환
├─ 차원 검증 (3072차원)
└─ FloatArray 반환
```

**에러 처리**:
- 3072차원 불일치 시 경고 로그
- 예외 발생 시 `IllegalStateException` 던짐

---

#### 3.4. EmbeddingApi

**위치**: `app/src/main/java/com/onair/mobile/assistant/data/intent/EmbeddingApi.kt`

**역할**:
- FastAPI 서버의 `/api/embedding` 엔드포인트 호출을 위한 Retrofit 인터페이스

**엔드포인트**:
```kotlin
@POST("/api/embedding")
suspend fun extractEmbedding(
    @Body request: EmbeddingRequest
): EmbeddingResponse
```

**요청 형식**:
```json
POST /api/embedding
{
  "text": "에러가 발생했어요"
}
```

**응답 형식**:
```json
{
  "embedding": [0.123, -0.456, 0.789, ...]  // 3072개 Float 값
}
```

---

#### 3.5. OnnxIntentClassifierDataSource

**위치**: `app/src/main/java/com/onair/mobile/assistant/data/intent/OnnxIntentClassifierDataSource.kt`

**역할**:
- ONNX Runtime을 사용하여 Intent Classifier 모델을 실행
- Assets에서 `intent_classifier.int8.onnx` 모델 로드

**모델 정보**:
- 입력: `embeddings` (3072차원 FloatArray) - Phi-3 임베딩
- 출력: `logits` (2차원) - [AI_SUPPORTER, OPERATOR]
- 학습: Phi-3 임베딩 + MLP 분류기 (PyTorch) → ONNX Export

**주요 메서드**:
```kotlin
init()
├─ OrtEnvironment 생성
├─ Assets에서 모델 파일 읽기 (models/intent_classifier.int8.onnx)
├─ OrtSession 생성
├─ 모델 정보 로깅 (입력/출력 이름, 메타데이터)
└─ isInitialized = true

classifyWithEmbedding(embedding, rawText)
├─ 초기화 검증
├─ 임베딩 차원 검증 (3072차원)
├─ ONNX 입력 Tensor 생성 ([batch=1, embedding_size=3072])
├─ 추론 실행 (ortSession.run())
├─ 출력 파싱 (parseOutput)
│   ├─ logits[0] = AI_SUPPORTER
│   ├─ logits[1] = OPERATOR
│   └─ 소프트맥스로 confidence 계산
├─ Tensor 정리 (close)
└─ IntentClassificationDto 반환

classify(text)  // Deprecated
└─ 임시 구현 (해시 기반 임베딩 사용)

textToEmbeddings(text)  // Deprecated
└─ 임시 구현 (실제 Phi-3 임베딩 필요)

parseOutput(outputs)
├─ logits 출력 가져오기
├─ 최대 점수 인덱스 찾기
├─ 인덱스 → IntentType 매핑
│   ├─ 0 → AI_SUPPORTER
│   └─ 1 → OPERATOR
└─ 소프트맥스로 confidence 계산

calculateConfidence(scores, index)
└─ 소프트맥스 적용: exp(scores[index]) / sum(exp(scores))

cleanup()
├─ OrtSession.close()
└─ OrtEnvironment.close()
```

**매핑 로직**:
- 노트북의 `LabelEncoder`: `['AI_SUPPORT', 'OPERATOR']`
- 따라서: `0` = `AI_SUPPORTER`, `1` = `OPERATOR`

---

### 4. Intent 분기 처리 계층

#### 4.1. DispatchIntentUseCase

**위치**: `app/src/main/java/com/onair/mobile/assistant/domain/usecase/DispatchIntentUseCase.kt`

**역할**:
- Intent 분류 결과에 따라 적절한 처리 경로로 분기
- `OPERATOR` → RTC Start (TODO)
- `AI_SUPPORTER` → CV → Clarification → RAG+LLM (TODO)

**의존성**:
- `DetectObjectUseCase` (nullable, Placeholder 파일 존재하나 구현 없음)
- `ClarifyQuestionUseCase` (nullable, Placeholder 파일 존재하나 구현 없음)
- `LlmRepository` (nullable, Placeholder 인터페이스만 존재)

**구현 상태**: ⚠️ 구조만 구현됨, 실제 API 호출은 TODO

**주요 메서드**:
```kotlin
invoke(intentResult)
├─ IntentType 분기 ✅ (구현됨)
│   ├─ OPERATOR → handleOperatorIntent()
│   ├─ AI_SUPPORTER → handleAiSupporterIntent()
│   └─ UNKNOWN → DispatchResult.Error()
└─ DispatchResult 반환 ✅ (구현됨)

handleOperatorIntent(intentResult)
└─ ⚠️ TODO: RTC Start 로직 구현
    현재는 성공 응답만 반환 (로깅만)

handleAiSupporterIntent(intentResult)
├─ tryExtractErrorFromCv(contextText)
│   └─ ⚠️ TODO: DetectObjectUseCase.detectError() 호출
│       현재는 null 반환
├─ buildClarifiedQuery(text)
│   └─ ⚠️ TODO: ClarifyQuestionUseCase.clarify() 호출
│       현재는 원본 텍스트 반환
└─ callRagLlm(queryForRag)
    └─ ⚠️ TODO: LlmRepository.generateRagResponse() 호출
        현재는 예외 던짐
```

**AI_SUPPORTER 플로우 (구조만 구현됨)**:
```
1. CV API 호출 시도 ⚠️ (구현 없음)
   └─ 현재는 null 반환
2. Clarification 수행 ⚠️ (구현 없음)
   └─ 현재는 원본 텍스트 반환
3. RAG+LLM API 호출 ⚠️ (구현 없음)
   └─ 현재는 예외 발생
```

---

#### ⚠️ Placeholder 파일들 (구현 없음)

다음 파일들은 **파일만 존재하고 실제 구현 코드가 없습니다**:

- `DetectObjectUseCase.kt` - 빈 클래스 (TODO 주석만)
- `ClarifyQuestionUseCase.kt` - 빈 클래스 (TODO 주석만)
- `LlmRepository.kt` - 빈 인터페이스 (TODO 주석만)

이 파일들은 향후 구현을 위한 구조만 정의되어 있습니다.

---

### 5. 데이터 모델

#### 5.1. IntentType

**위치**: `app/src/main/java/com/onair/mobile/assistant/domain/entity/IntentType.kt`

**정의**:
```kotlin
enum class IntentType(val value: String) {
    OPERATOR("operator"),           // 운영자 연결
    AI_SUPPORTER("ai_supporter"),   // AI 서포터 모드
    UNKNOWN("unknown")              // 알 수 없음
}
```

---

#### 5.2. IntentClassificationDto

**위치**: `app/src/main/java/com/onair/mobile/assistant/core/model/dto/IntentClassificationDto.kt`

**정의**:
```kotlin
data class IntentClassificationDto(
    val intentType: IntentType,
    val confidence: Float,  // 0.0 ~ 1.0
    val rawText: String
)
```

---

#### 5.3. EmbeddingRequest

**위치**: `app/src/main/java/com/onair/mobile/assistant/core/model/dto/EmbeddingRequest.kt`

**정의**:
```kotlin
data class EmbeddingRequest(
    val text: String
)
```

---

#### 5.4. EmbeddingResponse

**위치**: `app/src/main/java/com/onair/mobile/assistant/core/model/dto/EmbeddingRequest.kt` (같은 파일)

**정의**:
```kotlin
data class EmbeddingResponse(
    val embedding: List<Float>  // 3072차원
)
```

---

#### 5.5. DispatchResult

**위치**: `app/src/main/java/com/onair/mobile/assistant/domain/usecase/DispatchIntentUseCase.kt`

**정의**:
```kotlin
sealed class DispatchResult {
    data class Success(
        val type: IntentType,
        val message: String,
        val data: String
    ) : DispatchResult()
    
    data class Error(
        val message: String
    ) : DispatchResult()
}
```

---

## 🔧 세부 구현 로직

### 1. WebSocket 서버 초기화

```kotlin
webSocketServer = SttWebSocketServer(WS_PORT) { timestamp, text ->
    handleSttMessage(timestamp, text)
}
webSocketServer.start()
```

- 포트: 8080
- 연결: `ws://0.0.0.0:8080/ws/stt`
- 콜백: `onSttMessage(timestamp, text)`

---

### 2. HTTP 웹훅 서버 초기화

```kotlin
webhookServer = SttWebhookServer(WEBHOOK_PORT) {
    handleSttStart()
}
webhookServer.startServer()
```

- 포트: 8081
- 엔드포인트: `POST http://0.0.0.0:8081/webhook/stt_start`
- 콜백: `onSttStart()`

---

### 3. Phi-3 임베딩 추출 플로우

```kotlin
// 1. EmbeddingRepository 초기화
val embeddingRepository = EmbeddingRepository(
    baseUrl = "http://YOUR_FASTAPI_SERVER_URL:8000"
)

// 2. 임베딩 추출
val embedding = embeddingRepository.extractEmbedding(text)

// 3. Retrofit 호출
// POST http://<FastAPI_IP>:8000/api/embedding
// Request: {"text": "에러가 발생했어요"}
// Response: {"embedding": [3072차원 FloatArray]}

// 4. FloatArray 변환
val embeddingArray = response.embedding.toFloatArray()
```

---

### 4. ONNX 모델 추론 플로우

```kotlin
// 1. 모델 초기화 (앱 시작 시 한 번만)
dataSource.init()
// - Assets에서 모델 파일 읽기
// - OrtSession 생성

// 2. 임베딩으로 Intent 분류
val result = dataSource.classifyWithEmbedding(embedding, text)

// 3. 내부 처리
// - 임베딩 차원 검증 (3072)
// - ONNX 입력 Tensor 생성: [1, 3072]
// - 추론 실행: ortSession.run()
// - 출력 파싱: logits[0] = AI_SUPPORTER, logits[1] = OPERATOR
// - 소프트맥스로 confidence 계산
```

---

### 5. Intent 분기 처리 플로우

```kotlin
// 1. Intent 분류
val intentResult = classifyIntentUseCase(text)

// 2. 분기 처리
val dispatchResult = dispatchIntentUseCase(intentResult)

// 3. 결과 처리
when (dispatchResult) {
    is DispatchResult.Success -> {
        when (dispatchResult.type) {
            OPERATOR -> { /* RTC Start */ }
            AI_SUPPORTER -> { /* CV → Clarify → RAG+LLM */ }
        }
    }
    is DispatchResult.Error -> { /* 에러 처리 */ }
}
```

---

## 📦 의존성 및 라이브러리

### Gradle Dependencies (`app/build.gradle`)

```gradle
// Android 기본
implementation "androidx.core:core-ktx:1.13.1"
implementation "androidx.appcompat:appcompat:1.7.0"
implementation "com.google.android.material:material:1.12.0"

// WebSocket 서버 (라즈베리파이로부터 STT 텍스트 수신)
implementation("org.java-websocket:Java-WebSocket:1.5.6")

// HTTP 서버 (라즈베리파이로부터 stt_start 알림 수신)
implementation("org.nanohttpd:nanohttpd:2.3.1")

// JSON 처리
implementation("org.json:json:20231013")

// Retrofit (FastAPI 서버 호출용)
implementation "com.squareup.retrofit2:retrofit:2.9.0"
implementation "com.squareup.retrofit2:converter-gson:2.9.0"

// ONNX Runtime
implementation "com.microsoft.onnxruntime:onnxruntime-android:1.18.0"
```

---

### Assets 파일

```
app/src/main/assets/models/intent_classifier.int8.onnx
- ONNX Intent Classifier 모델 파일
- 입력: 3072차원 FloatArray (Phi-3 임베딩)
- 출력: 2차원 logits (AI_SUPPORTER, OPERATOR)
```

---

## ⚠️ 미구현 항목

### 1. FastAPI 서버 URL 설정

**위치**: `MainActivitySttServer.kt:49`

```kotlin
val embeddingRepository = EmbeddingRepository(
    baseUrl = "http://YOUR_FASTAPI_SERVER_URL:8000"  // TODO: 실제 서버 URL로 변경
)
```

**작업**: 실제 FastAPI 서버 IP 주소로 변경 필요

---

### 2. RTC Start 로직

**위치**: `DispatchIntentUseCase.kt:54-71`

```kotlin
private suspend fun handleOperatorIntent(intentResult: IntentClassificationDto): DispatchResult {
    // TODO: RTC Start 로직 구현
    // rtcRepository.startConnection(...)
}
```

**작업**: RTC 연결 시작 로직 구현 필요

---

### 3. CV API 연동

**위치**: `DispatchIntentUseCase.kt:116-132`

```kotlin
private suspend fun tryExtractErrorFromCv(contextText: String): String? {
    // TODO: DetectObjectUseCase의 실제 API 호출 메서드 확인 후 연동
    // val cvResult = detectObjectUseCase.detectError(...)
}
```

**작업**:
- `DetectObjectUseCase` 구현
- Python YOLOv11nano API 호출 로직 추가

---

### 4. Clarification API 연동

**위치**: `DispatchIntentUseCase.kt:139-155`

```kotlin
private suspend fun buildClarifiedQuery(originalText: String): String {
    // TODO: ClarifyQuestionUseCase의 실제 API 호출 메서드 확인 후 연동
    // val clarified = clarifyQuestionUseCase.clarify(originalText)
}
```

**작업**:
- `ClarifyQuestionUseCase` 구현
- Clarification Model API 호출 로직 추가

---

### 5. RAG+LLM API 연동

**위치**: `DispatchIntentUseCase.kt:164-180`

```kotlin
private suspend fun callRagLlm(query: String): String {
    // TODO: LlmRepository의 실제 API 호출 메서드 확인 후 연동
    // val response = llmRepository.generateRagResponse(query)
}
```

**작업**:
- `LlmRepository` 구현체 추가
- FastAPI 서버의 RAG+LLM API 호출 로직 추가

---

### 6. UI 업데이트

**위치**: `MainActivitySttServer.kt`

**작업**:
- STT 텍스트 표시 (TextView 등)
- Intent 분류 결과 표시
- "듣고 있습니다..." 표시 (`handleSttStart` 호출 시)
- RTC 연결 상태 표시
- Vision Analyzer 결과 또는 LLM 응답 표시

---

## 📝 요약

### ✅ 실제 구현 완료 항목 (코드 작성됨)

1. **WebSocket 서버** (`SttWebSocketServer.kt`)
   - 라즈베리파이로부터 STT 텍스트 수신
   - JSON 파싱 및 에러 처리
   - 연결 관리

2. **HTTP 웹훅 서버** (`SttWebhookServer.kt`)
   - 라즈베리파이로부터 stt_start 알림 수신
   - POST 요청 처리

3. **STT Repository** (`SttRepositoryImpl.kt`, `RaspberryPiTextReceiver.kt`)
   - 라즈베리파이 텍스트 수신 및 저장
   - StateFlow로 실시간 업데이트

4. **FastAPI 서버 호출** (`EmbeddingRepository.kt`, `EmbeddingApi.kt`)
   - Phi-3 임베딩 추출 API 호출
   - Retrofit 기반 HTTP 클라이언트
   - 3072차원 FloatArray 수신

5. **ONNX Intent Classifier** (`OnnxIntentClassifierDataSource.kt`)
   - Assets에서 모델 파일 로드
   - ONNX Runtime 세션 생성
   - 3072차원 임베딩 입력 → Intent 분류
   - 소프트맥스로 confidence 계산

6. **Intent 분류 UseCase** (`ClassifyIntentUseCase.kt`, `IntentRepositoryImpl.kt`)
   - FastAPI → 임베딩 추출 → ONNX 모델 실행
   - IntentClassificationDto 반환

7. **Intent 분기 처리 구조** (`DispatchIntentUseCase.kt`)
   - IntentType에 따른 분기 로직
   - DispatchResult 반환 구조
   - ⚠️ 실제 API 호출은 TODO (CV, Clarification, RAG+LLM)

### ⚠️ 부분 구현 항목 (구조만 있음)

1. **DispatchIntentUseCase** - 분기 로직은 있으나 실제 API 호출 미구현
   - `handleOperatorIntent()` - RTC Start 로직 TODO
   - `handleAiSupporterIntent()` - CV/Clarification/RAG+LLM 호출 TODO

### ❌ 미구현 항목 (파일만 존재, 코드 없음)

1. **DetectObjectUseCase** - 빈 클래스 (TODO 주석만)
2. **ClarifyQuestionUseCase** - 빈 클래스 (TODO 주석만)
3. **LlmRepository** - 빈 인터페이스 (TODO 주석만)

### 📝 설정 필요 항목

1. **FastAPI 서버 URL** (`MainActivitySttServer.kt:49`)
   - 현재: `"http://YOUR_FASTAPI_SERVER_URL:8000"`
   - 실제 서버 IP로 변경 필요

2. **UI 업데이트**
   - STT 텍스트 표시
   - Intent 분류 결과 표시
   - 처리 상태 표시

---

## 🔗 관련 파일 목록

### 핵심 파일
- `MainActivitySttServer.kt` - Entry Point
- `SttWebSocketServer.kt` - WebSocket 서버
- `SttWebhookServer.kt` - HTTP 웹훅 서버
- `SttRepositoryImpl.kt` - STT Repository
- `IntentRepositoryImpl.kt` - Intent Repository
- `EmbeddingRepository.kt` - FastAPI 임베딩 호출
- `OnnxIntentClassifierDataSource.kt` - ONNX 모델 실행
- `DispatchIntentUseCase.kt` - Intent 분기 처리

### 데이터 모델
- `IntentType.kt` - Intent 타입 enum
- `IntentClassificationDto.kt` - Intent 분류 결과 DTO
- `EmbeddingRequest.kt` / `EmbeddingResponse.kt` - 임베딩 요청/응답 DTO

### ⚠️ Placeholder 파일 (구현 없음)
다음 파일들은 파일만 존재하고 실제 구현 코드가 없습니다:
- `DetectObjectUseCase.kt` - 빈 클래스 (TODO 주석만)
- `ClarifyQuestionUseCase.kt` - 빈 클래스 (TODO 주석만)
- `LlmRepository.kt` - 빈 인터페이스 (TODO 주석만)

---

**작성일**: 2024년
**버전**: 1.0

