# 🏗️ 전체 서비스 아키텍처 및 로직

## 📊 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────┐
│                  라즈베리파이 제로 (Python)               │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 1. 마이크 스트림 수집 (pyaudio/sounddevice)      │   │
│  │ 2. VAD (WebRTC) → 말 시작/종료 감지              │   │
│  │ 3. Google Cloud STT REST API 호출                │   │
│  │ 4. STT 텍스트 → WebSocket 전송                   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                        │
                        │ WebSocket (ws://<Android_IP>:8080/ws/stt)
                        │ JSON: {"timestamp": "...", "text": "..."}
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Android 앱 (Kotlin)                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 5. WebSocket 서버 수신                           │   │
│  │ 6. Intent Classifier (ONNX)                      │   │
│  │ 7. Intent별 처리 로직                            │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 🔄 상세 처리 흐름

### Phase 1: 라즈베리파이 (Python)

```
1. 마이크 입력
   └─> pyaudio/sounddevice로 실시간 스트림 캡처

2. VAD (Voice Activity Detection)
   └─> WebRTC VAD로 음성 에너지 분석
       ├─ "말 시작" 감지 → 녹음 시작
       └─ 0.8초 이상 무음 → 녹음 종료

3. Google Cloud STT
   └─> 메모리에서 직접 REST API 호출
       ├─ 음성 → Base64 인코딩
       └─ 텍스트 결과 수신

4. WebSocket 전송
   └─> Android 기기로 JSON 전송
       {
         "timestamp": "2025-10-29T14:00:00Z",
         "text": "밸브를 왼쪽으로 두 바퀴 돌리세요"
       }
```

### Phase 2: Android 앱 (Kotlin)

#### 2-1. WebSocket 서버 수신 (`MainActivitySttServer.kt`)

```kotlin
onCreate() {
    // WebSocket 서버 시작 (포트 8080)
    server = SttWebSocketServer(8080) { timestamp, text ->
        handleSttMessage(timestamp, text)
    }
    server.start()
}

handleSttMessage(timestamp, text) {
    // 라즈베리파이로부터 텍스트 수신
    sttRepository.receiveFromRaspberryPi(text)
    
    // Intent Classifier 호출
    val intentResult = classifyIntentUseCase(text)
    
    // Intent별 처리
    handleIntent(intentResult)
}
```

#### 2-2. STT Repository (`SttRepositoryImpl.kt`)

```kotlin
receiveFromRaspberryPi(text: String) {
    // RaspberryPiTextReceiver에 텍스트 저장
    raspberryPiReceiver.receiveText(text)
    
    // Flow로 실시간 업데이트 (필요 시)
    // getRaspberryPiTextFlow()로 구독 가능
}
```

**주요 기능:**
- 라즈베리파이 텍스트 수신 저장
- 모바일 내장 마이크 STT도 지원 (선택적)

#### 2-3. Intent Classifier (`OnnxIntentClassifierDataSource.kt`)

```kotlin
classify(text: String) {
    // 1. 텍스트 → 임베딩 변환
    val embeddings = textToEmbeddings(text)
    
    // 2. ONNX 모델 추론
    val outputs = ortSession.run(mapOf("embeddings" to inputTensor))
    
    // 3. 결과 파싱
    val intentType = parseOutput(outputs)
    
    return IntentClassificationDto(
        intentType = VALVE_CONTROL | QUESTION | COMMAND | UNKNOWN,
        confidence = 0.95f,
        rawText = text
    )
}
```

**모델 정보:**
- 경로: `app/src/main/assets/models/intent_classifier.int8.onnx`
- 입력: embeddings (텍스트 임베딩 벡터)
- 출력: logits (Intent 분류 점수)

**Intent 타입:**
- `VALVE_CONTROL`: 밸브 제어 (예: "밸브를 왼쪽으로 두 바퀴 돌리세요")
- `QUESTION`: 질문 (예: "밸브 위치가 어디야?")
- `COMMAND`: 명령 (예: "시스템 재시작")
- `UNKNOWN`: 알 수 없음

#### 2-4. Intent별 처리 (`MainActivitySttServer.kt`)

```kotlin
handleIntent(intentResult) {
    when (intentResult.intentType) {
        VALVE_CONTROL -> {
            // TODO: 밸브 제어 로직
            // 예: 밸브 컨트롤러와 통신
        }
        QUESTION -> {
            // TODO: 질문 처리 로직
            // 예: RAG 검색 또는 LLM 응답
        }
        COMMAND -> {
            // TODO: 명령 처리 로직
            // 예: 시스템 명령 실행
        }
        UNKNOWN -> {
            // 알 수 없는 Intent 처리
        }
    }
}
```

## 📁 주요 파일 구조

```
app/src/main/java/com/onair/mobile/
├── MainActivitySttServer.kt          # WebSocket 서버 엔트리 포인트
│
├── assistant/
│   ├── data/
│   │   ├── stt/
│   │   │   ├── SttWebSocketServer.kt          # WebSocket 서버
│   │   │   ├── SttRepositoryImpl.kt           # STT Repository
│   │   │   ├── RaspberryPiTextReceiver.kt     # 라즈베리파이 텍스트 수신
│   │   │   └── AndroidSttDataSource.kt        # 모바일 내장 마이크 STT (선택)
│   │   │
│   │   └── intent/
│   │       ├── OnnxIntentClassifierDataSource.kt  # ONNX 모델 추론
│   │       └── IntentRepositoryImpl.kt            # Intent Repository
│   │
│   ├── domain/
│   │   ├── entity/
│   │   │   └── IntentType.kt               # Intent 타입 정의
│   │   │
│   │   ├── repository/
│   │   │   ├── SttRepository.kt             # STT Repository 인터페이스
│   │   │   └── IntentRepository.kt          # Intent Repository 인터페이스
│   │   │
│   │   └── usecase/
│   │       ├── StartSttUseCase.kt          # STT 시작 UseCase
│   │       └── ClassifyIntentUseCase.kt    # Intent 분류 UseCase
│   │
│   └── core/
│       └── model/
│           └── dto/
│               └── IntentClassificationDto.kt  # Intent 분류 결과 DTO
│
└── assets/
    └── models/
        └── intent_classifier.int8.onnx      # ONNX 모델 파일
```

## 🔄 데이터 흐름 다이어그램

```
라즈베리파이:
  마이크 입력
    ↓
  VAD 감지
    ↓
  Google STT REST API
    ↓
  텍스트: "밸브를 왼쪽으로 두 바퀴 돌리세요"
    ↓
  WebSocket 전송 (JSON)
    ↓
Android:
  SttWebSocketServer.onMessage()
    ↓
  SttRepository.receiveFromRaspberryPi()
    ↓
  ClassifyIntentUseCase()
    ↓
  OnnxIntentClassifierDataSource.classify()
    ↓
  IntentClassificationDto {
    intentType: VALVE_CONTROL,
    confidence: 0.95,
    rawText: "밸브를 왼쪽으로 두 바퀴 돌리세요"
  }
    ↓
  handleIntent()
    ↓
  Intent별 처리 로직 (TODO)
```

## 🎯 현재 구현 상태

### ✅ 완료된 기능

1. **WebSocket 서버**
   - 라즈베리파이로부터 STT 텍스트 수신
   - JSON 파싱
   - 에러 처리

2. **STT Repository**
   - 라즈베리파이 텍스트 수신 저장
   - Flow로 실시간 구독 가능

3. **Intent Classifier**
   - ONNX 모델 로드
   - 텍스트 → Intent 분류
   - 4가지 Intent 타입 지원

4. **Intent 처리 구조**
   - Intent별 분기 처리 준비 완료

### ⏳ TODO (향후 구현)

1. **텍스트 임베딩 개선**
   - 현재: 간단한 해시 기반 임베딩
   - 필요: phi-3 토크나이저 적용

2. **Intent별 처리 로직**
   - `VALVE_CONTROL`: 밸브 제어 API 호출
   - `QUESTION`: RAG 또는 LLM 응답
   - `COMMAND`: 시스템 명령 실행

3. **UI 업데이트**
   - Intent 분류 결과 표시
   - 처리 상태 표시

## 📊 로그 예시

### 정상 동작 시나리오

```
[라즈베리파이]
🎤 음성 감지 시작
✅ VAD: 말 시작
🔄 Google STT 호출 중...
✅ STT 결과: "밸브를 왼쪽으로 두 바퀴 돌리세요"
📤 WebSocket 전송

[Android]
🚀 WebSocket 서버 시작: ws://0.0.0.0:8080/ws/stt
✅ 라즈베리파이 연결됨: /192.168.0.15:52341
📩 STT 텍스트 수신: {"timestamp":"...","text":"밸브를 왼쪽으로 두 바퀴 돌리세요"}
🧠 STT 텍스트 처리: [2025-10-29T14:00:00Z] 밸브를 왼쪽으로 두 바퀴 돌리세요
✅ Intent 분류 완료: valve_control (신뢰도: 0.95)
🔧 밸브 제어 Intent: 밸브를 왼쪽으로 두 바퀴 돌리세요
```

## 🔧 기술 스택

### Android (Kotlin)
- **WebSocket**: Java-WebSocket 1.5.6
- **ONNX Runtime**: onnxruntime-android 1.18.0
- **JSON**: org.json:json 20231013
- **Coroutines**: kotlinx-coroutines (이미 포함)

### 라즈베리파이 (Python)
- **마이크**: pyaudio 또는 sounddevice
- **VAD**: webrtcvad
- **STT**: Google Cloud Speech-to-Text REST API
- **WebSocket**: websockets 라이브러리

## ✅ 완료!

전체 서비스 로직이 구현되었습니다!

다음 단계: Intent별 처리 로직 구현 및 UI 업데이트

