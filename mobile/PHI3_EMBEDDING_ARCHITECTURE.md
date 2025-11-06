# Phi-3 임베딩 추출 구조 정리

## 전체 흐름

```
1. 라즈베리파이: STT 텍스트 → Android
   예: "사람 불러줘"

2. Android: 텍스트 → FastAPI 서버로 전송
   POST /api/embedding
   { "text": "사람 불러줘" }

3. FastAPI 서버: 텍스트 → Phi-3 임베딩 추출
   - Phi-3 모델 실행
   - last_hidden_state.mean(dim=1)
   - → 3072차원 FloatArray 반환

4. Android: 3072차원 FloatArray 수신
   [0.123, -0.456, 0.789, ...] (3072개)

5. Android: intent_classifier.int8.onnx 모델 입력
   - 입력: 3072차원 FloatArray
   - 출력: logits [OPERATOR, AI_SUPPORTER]
   - → Intent 분류 완료!
```

## 핵심 정리

**서버가 모바일로 넘겨주는 것:**
- **3072차원 FloatArray (임베딩 벡터)**

**모바일의 intent_classifier.int8.onnx 모델이 기반으로 하는 것:**
- **3072차원 FloatArray (Phi-3 임베딩 벡터)**
- 이 임베딩 벡터를 입력으로 받아서 Intent 분류 수행

## 구현된 파일

### Android (Kotlin)

1. **EmbeddingRequest.kt** - 임베딩 요청 DTO
2. **EmbeddingApi.kt** - Retrofit API 인터페이스
3. **EmbeddingRepository.kt** - FastAPI 서버 호출 Repository
4. **OnnxIntentClassifierDataSource.kt** - `classifyWithEmbedding()` 메서드 추가
5. **IntentRepositoryImpl.kt** - EmbeddingRepository 통합
6. **MainActivitySttServer.kt** - EmbeddingRepository 주입

### FastAPI 서버 (Python) - 구현 필요

```python
from fastapi import FastAPI
from transformers import AutoModel, AutoTokenizer
import torch
import numpy as np

app = FastAPI()

# Phi-3 모델 로드 (최초 1회만)
MODEL_NAME = "microsoft/phi-3-mini-4k-instruct"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)
model.eval()

@app.post("/api/embedding")
async def extract_embedding(request: dict):
    text = request["text"]
    
    # 토크나이징
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    
    # Phi-3 모델 실행
    with torch.no_grad():
        outputs = model(**inputs)
    
    # last_hidden_state.mean(dim=1) → 3072차원 벡터
    embedding = outputs.last_hidden_state.mean(dim=1)[0].cpu().numpy()
    
    # Float 리스트로 변환
    embedding_list = embedding.tolist()
    
    return {"embedding": embedding_list}
```

## 사용 방법

### 1. FastAPI 서버 실행

```bash
# ai_server 프로젝트에서
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Android 앱 설정

`MainActivitySttServer.kt`에서 FastAPI 서버 URL 설정:

```kotlin
val embeddingRepository = EmbeddingRepository(
    baseUrl = "http://192.168.0.100:8000"  // 실제 서버 IP로 변경
)
```

### 3. 동작 확인

1. 라즈베리파이에서 STT 텍스트 전송
2. Android가 FastAPI 서버에 임베딩 요청
3. 서버가 Phi-3 임베딩 반환
4. Android가 ONNX 모델로 Intent 분류
5. Intent 결과 출력

## 참고사항

- **임베딩 차원**: 반드시 3072차원이어야 합니다
- **서버 URL**: Android 앱과 FastAPI 서버가 같은 네트워크에 있어야 합니다
- **에러 처리**: 서버 연결 실패 시 임시 해시 기반 임베딩 사용 (성능 저하)

