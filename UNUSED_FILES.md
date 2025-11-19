# 사용되지 않는 파일 목록

## 📋 정리 대상 파일

다음 파일들은 현재 서비스에서 사용되지 않습니다:

### 1. `ai_server/rag_server/app/services/chat_service.py`
- **상태**: 사용되지 않음
- **이유**: `socket_handler.py`에서 import되지 않음
- **내용**: `rag_chat()` 함수가 정의되어 있으나 실제로 호출되지 않음
- **대체**: `socket_handler.py`에서 직접 `hybrid_retrieve`, `rerank`, `llm_generate_answer` 등을 사용

### 2. `ai_server/rag_server/app/services/clarify_service.py`
- **상태**: 사용되지 않음
- **이유**: `socket_handler.py`에서 import되지 않음
- **내용**: `ClarifyService` 클래스가 정의되어 있으나 실제로 사용되지 않음
- **대체**: `socket_handler.py`에서 `answerability.py`의 함수들을 직접 사용

### 3. `ai_server/rag_server/app/services/generator_service.py`
- **상태**: 사용되지 않음
- **이유**: import되지 않음
- **내용**: `simple_generate_answer()` 함수만 있고 실제로 사용되지 않음
- **대체**: `generator.py`의 `llm_generate_answer()` 사용

### 4. `ai_server/rag_server/app/ar/video_handle.py`
- **상태**: 사용되지 않음
- **이유**: `socket_manager`를 import하는데, `ai_server/rag_server/app/sockets/`에는 `socket_manager.py`가 없음
- **내용**: AR 비디오 프레임 처리 로직이지만 실제로 사용되지 않음
- **참고**: `ai_ar`와 `raspi` 폴더에 별도의 `socket_manager.py`가 있음

### 5. `ai_server/rag_server/app/utils/retry.py`
- **상태**: 사용되지 않음
- **이유**: `utils/__init__.py`에서 export하지만 실제로 import되지 않음
- **내용**: `retry_with_backoff()` 함수가 정의되어 있으나 사용되지 않음

### 6. `ai_server/rag_server/app/services/llm_service.py` (부분적)
- **상태**: 부분 사용
- **사용됨**: `clarify_query()` 함수만 사용 (socket_handler.py에서)
- **사용 안 됨**: `cosine_similarity()` 함수는 사용되지 않음 (clarify_service.py에서만 import되나 clarify_service.py 자체가 사용되지 않음)

## 🗑️ 삭제 권장 파일

다음 파일들은 삭제해도 서비스에 영향이 없습니다:

1. `ai_server/rag_server/app/services/chat_service.py`
2. `ai_server/rag_server/app/services/clarify_service.py`
3. `ai_server/rag_server/app/services/generator_service.py`
4. `ai_server/rag_server/app/ar/video_handle.py`
5. `ai_server/rag_server/app/utils/retry.py` (또는 `utils/__init__.py`에서 export 제거)

## ⚠️ 주의사항

- `llm_service.py`는 `clarify_query()` 함수가 사용되므로 삭제하지 마세요.
- `llm_service.py`의 `cosine_similarity()` 함수만 사용되지 않으므로, 필요시 해당 함수만 제거할 수 있습니다.

