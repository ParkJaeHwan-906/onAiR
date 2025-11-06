# 🎤 AI Assistant Mobile App

라즈베리파이 제로와 연동하여 음성 명령을 처리하는 Android 앱입니다.

## 🏗️ 아키텍처

```
라즈베리파이 제로 (Python)
  └─> 마이크 → VAD → Google STT → WebSocket 전송
                ↓
       Android 앱 (Kotlin)
         └─> WebSocket 서버 수신
         └─> Intent Classifier (ONNX)
         └─> Intent별 처리
```

## 📁 주요 파일

### Entry Point
- `MainActivitySttServer.kt` - WebSocket 서버 시작 및 Intent 처리

### Data Layer
- `SttWebSocketServer.kt` - 라즈베리파이로부터 STT 텍스트 수신
- `OnnxIntentClassifierDataSource.kt` - ONNX 모델로 Intent 분류
- `SttRepositoryImpl.kt` - STT Repository 구현
- `IntentRepositoryImpl.kt` - Intent Repository 구현

### Domain Layer
- `ClassifyIntentUseCase.kt` - Intent 분류 UseCase
- `IntentType.kt` - Intent 타입 정의

## 🚀 사용 방법

1. Android Studio에서 `MainActivitySttServer` 실행
2. 안드로이드 기기 IP 확인
3. 라즈베리파이에서 `ws://<안드로이드_IP>:8080/ws/stt` 연결
4. 음성 명령 전송

## 📦 의존성

- Java-WebSocket: 1.5.6
- ONNX Runtime: 1.18.0
- JSON: org.json:json

## 📝 상세 문서

자세한 내용은 `SERVICE_ARCHITECTURE.md`를 참고하세요.

