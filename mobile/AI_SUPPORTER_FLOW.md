# AI Supporter 플로우 구조

## 🔄 AI Supporter 처리 흐름

```
IntentType: AI_SUPPORTER
    ↓
1. CV API 호출 (Python YOLOv11nano)
    ├─ 성공 → 에러 상황 추출
    └─ 실패 → null
    ↓
2. CV 결과에 따라 분기
    ├─ CV 성공 → 에러 상황 → RAG+LLM API
    └─ CV 실패 → Clarification API → 구체화된 질문 → RAG+LLM API
    ↓
3. 서버 RAG + LLM API 호출 (FastAPI)
    └─ 서버에서 EC2로 전달
    ↓
4. 응답 반환 → TTS로 전송
```

## 📁 구현 구조

### 1. DispatchIntentUseCase
- **역할**: Intent에 따른 분기 처리
- **의존성 주입**:
  - `DetectObjectUseCase?` - CV API 호출
  - `ClarifyQuestionUseCase?` - Clarification API 호출
  - `LlmRepository?` - RAG+LLM API 호출

### 2. API 호출 구조

#### CV API (DetectObjectUseCase)
```kotlin
// TODO: Python YOLOv11nano API 호출
// 에러 상황 추출 성공 시: String 반환
// 실패 시: null 반환
```

#### Clarification API (ClarifyQuestionUseCase)
```kotlin
// TODO: Clarification Model API 호출
// 구체화된 질문 1개 반환
```

#### RAG + LLM API (LlmRepository)
```kotlin
// TODO: FastAPI 서버로 요청
// 서버에서 EC2로 전달하여 RAG+LLM 처리
// 응답 텍스트 반환
```

## ⚠️ 중요 사항

1. **CV 실패해도 진행**: CV로 에러 상황 추출을 시도하지만, 실패해도 계속 진행
2. **서버에서 LLM 처리**: Kotlin에서는 API 호출만 하고, 서버(FastAPI)에서 EC2로 전달하여 RAG+LLM 처리
3. **단일 진입점**: 최종적으로는 항상 RAG+LLM API 호출로 진입
   - CV 성공 → 에러 상황 → RAG+LLM
   - CV 실패 → Clarification → 구체화된 질문 → RAG+LLM

## 📝 TODO

1. **DetectObjectUseCase 구현**
   - Python YOLOv11nano API 호출
   - 에러 상황 추출 결과 반환

2. **ClarifyQuestionUseCase 구현**
   - Clarification Model API 호출
   - 구체화된 질문 반환

3. **LlmRepository 구현**
   - FastAPI 서버로 RAG+LLM 요청
   - 서버 응답 반환

## ✅ 현재 상태

- 구조 완성: IntentDispatcher에서 API 호출 흐름 준비 완료
- API 연동: TODO로 표시, 실제 API 구현 시 주입

