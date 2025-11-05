# 세션 관리 구조 및 상태 전이 다이어그램

## 🎯 세션 상태 전이 다이어그램 (State Machine)

```
┌─────────────────────────────────────────────────────────────────┐
│                    세션 생명주기 (Session Lifecycle)              │
└─────────────────────────────────────────────────────────────────┘

① INITIAL (초기 상태)
   │
   │ 모바일 앱: UUID 생성
   │ POST /rag/chat (session_id: "abc-123")
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│ ② ACTIVE (활성 세션)                                         │
│                                                              │
│  - Redis에 질문 저장                                          │
│  - Hybrid Search 수행                                        │
│  - Evidence Check 수행                                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
   │
   ├─ [Evidence 충분] → ③ ANSWERING
   │
   └─ [Evidence 부족] → ④ CLARIFYING
                              │
                              │ 사용자 추가 설명 입력
                              │ (동일 session_id로 재호출)
                              │
                              └─→ ② ACTIVE (재평가)
                                   │
                                   └─ [Evidence 충분] → ③ ANSWERING
                                   
┌──────────────────────────────────────────────────────────────┐
│ ③ ANSWERING (답변 생성)                                       │
│                                                              │
│  - GPT-4o로 최종 답변 생성                                     │
│  - Redis에 답변 저장                                          │
│  - 세션 초기화 (memory.clear_history)                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│ ④ TERMINATED (세션 종료)                                     │
│                                                              │
│  - Redis 세션 데이터 삭제                                      │
│  - 다음 질문은 새 UUID로 시작                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 상태 전이 테이블

| 상태 | 설명 | 세션 ID | Redis 상태 | 전이 조건 |
|------|------|---------|-----------|----------|
| **INITIAL** | 세션 시작 전 | 생성 전 | - | 모바일 앱이 UUID 생성 |
| **ACTIVE** | 활성 대화 중 | ✅ 유지 | 히스토리 저장 중 | 질문 입력, Clarify 중 |
| **CLARIFYING** | 질문 구체화 중 | ✅ 유지 | 히스토리 누적 | Evidence 부족 (RED) |
| **ANSWERING** | 최종 답변 생성 | ✅ 유지 | 답변 저장 | Evidence 충분 (GREEN) |
| **TERMINATED** | 세션 종료 | 삭제됨 | Redis 키 삭제 | GPT-4o 답변 완료 |

---

## 🔄 전체 플로우 상세도

```
┌─────────────────┐
│  라즈베리파이      │
│  (STT만 수행)     │
└────────┬─────────┘
         │
         │ 음성 → 텍스트 변환
         │ WebSocket 전송
         ▼
┌─────────────────┐
│   모바일 앱      │
│                 │
│ ① UUID 생성      │
│    session_id = │
│    UUID.random() │
│                 │
│ ② Intent 분류   │
│    → AI_Supporter│
└────────┬─────────┘
         │
         │ POST /rag/chat
         │ {query, session_id}
         ▼
┌─────────────────────────────────────┐
│      FastAPI 서버                    │
│                                     │
│ ③ Redis 히스토리 로드                 │
│    if session_id:                   │
│      history = get_history(id)      │
│                                     │
│ ④ Hybrid Search + Rerank            │
│                                     │
│ ⑤ Evidence Sufficiency Check       │
│    ├─ RED → Clarify 필요            │
│    ├─ YELLOW → 답변 가능 (추가 정보 권장)│
│    └─ GREEN → 답변 생성 가능         │
└────────┬─────────────────────────────┘
         │
         ├─ [RED] ──────────────────────┐
         │                               │
         │ ⑥ Gemini Flash Clarify       │
         │    - 누락 정보 추출            │
         │    - Clarify 가이드 생성       │
         │    - Redis에 저장             │
         │                               │
         │    응답: {                    │
         │      answerable: false,      │
         │      need_clarify: true,     │
         │      clarify_guidance: "...", │
         │      ...                     │
         │    }                          │
         │                               │
         │    ┌─────────────────────────┘
         │    │
         │    ▼
         │ ⑦ 모바일 앱에 Clarify 표시
         │    ┌─────────────────────────┐
         │    │                         │
         │    ▼                         │
         │ ⑧ 사용자 추가 설명 입력        │
         │    (라즈베리파이 → 모바일)      │
         │    ┌─────────────────────────┐
         │    │                         │
         │    ▼                         │
         │ ⑨ POST /rag/chat 재호출      │
         │    (동일 session_id)         │
         │    ┌─────────────────────────┐
         │    │                         │
         │    └─→ ③으로 돌아가서 재평가  │
         │
         └─ [GREEN] ────────────────────┐
                                         │
           ⑩ GPT-4o 답변 생성            │
           - 검색된 문서 기반 답변         │
           - Redis에 답변 저장            │
           - memory.clear_history(id)    │
                                         │
           ⑪ 응답 반환                   │
           {                             │
             answerable: true,          │
             result: {                  │
               answer: "...",           │
               citations: [...]         │
             }                          │
           }                            │
                                         │
           ⑫ 세션 종료                   │
           (다음 질문은 새 UUID로)        │
                                         │
           └─────────────────────────────┘
```

---

## 🧩 컴포넌트별 역할 정리

### 🔊 라즈베리파이
- **역할**: 음성 입력 → STT → 텍스트 변환
- **세션 관리**: ❌ 없음 (단순 입출력만)
- **출력**: WebSocket으로 모바일 앱에 텍스트 전송

### 📱 모바일 앱
- **역할**: 
  - Intent 분류 (Phi-3 Embedding)
  - 세션 ID 생성 및 관리
  - FastAPI 서버와 통신
- **세션 관리**: ✅ **주체**
  - 최초 질문 시: `UUID.randomUUID()` 생성
  - Clarify 루프 동안: **동일 session_id 유지**
  - 최종 답변 수신 후: 새 세션 준비 (또는 유지)
- **중요**: 모든 Clarify turn에서 같은 `session_id`를 보내야 함

### 🧠 FastAPI 서버
- **역할**: 
  - RAG 검색 및 Evidence 평가
  - Clarify 가이드 생성 (Gemini Flash)
  - 최종 답변 생성 (GPT-4o)
  - Redis 기반 세션 히스토리 관리
- **세션 관리**: ✅ **Redis 기반**
  - `session_id`로 히스토리 로드
  - Clarify 중: 히스토리 누적 저장
  - 답변 완료: 세션 초기화 (`clear_history`)

---

## 🔁 Clarify 반복 구조 (상세)

```
Turn 1:
  사용자: "기계가 작동 안 해요"
  session_id: "abc-123"
  ↓
  서버: Evidence 부족 → RED
  ↓
  Gemini Flash: "어떤 부품인가요?"
  ↓
  Redis 저장:
    - user query: "기계가 작동 안 해요"
    - system evidence: {...}
    - clarify_guidance: "어떤 부품인가요?"

Turn 2 (동일 session_id):
  사용자: "송풍기가요"
  session_id: "abc-123"  ← 같은 ID!
  ↓
  서버: Redis에서 이전 질문 로드
  effective_query = "기계가 작동 안 해요 \n송풍기가요"
  ↓
  서버: Evidence 재평가
  ↓
  [충분] → GPT-4o 답변 생성
  [부족] → 다시 Clarify (Turn 3)
```

---

## 💡 세션 종료 시점

### 현재 구현 (코드 기반)

```python
# 라인 154: GPT-4o 답변 생성 후
memory.clear_history(session_id)
```

**종료 조건**: 
- ✅ GPT-4o가 최종 답변 생성 완료
- ✅ 서버에서 명시적으로 세션 삭제

**종료되지 않는 경우**:
- ❌ Clarify 단계에서는 세션 유지
- ❌ YELLOW 상태에서도 세션 유지 (추가 정보 권장만)

---

## 🎯 핵심 설계 원칙

### 1. 세션 = 하나의 완전한 질문-답변 사이클

> **"Clarify를 포함한 모든 turn이 하나의 세션으로 묶임"**

### 2. 세션 ID는 클라이언트(모바일) 주체

> **"모바일 앱이 생성하고 관리하는 것이 가장 단순하고 명확함"**

### 3. 세션 종료 = 최종 답변 생성 시점

> **"GPT-4o가 실행되면 그 세션은 종료되고, 다음 질문은 새 세션으로 시작"**

---

## 📝 코드 레벨 확인 사항

### ✅ 현재 구현과 일치하는 부분

1. **세션 ID 선택 필드**
   ```python
   session_id: str | None = None
   ```

2. **히스토리 로드 조건부**
   ```python
   if session_id:
       prev = memory.get_history(session_id)
   ```

3. **Clarify 단계에서 세션 유지**
   ```python
   if session_id:
       memory.append_event(session_id, {...})
   ```

4. **답변 완료 후 세션 초기화**
   ```python
   memory.clear_history(session_id)
   ```

### ⚠️ 개선 가능한 부분 (선택사항)

1. **Redis TTL 설정 추가** (명시적 삭제 + 자동 만료 백업)
   ```python
   # 현재: 명시적 삭제만
   # 개선: TTL도 설정 (예: 10분)
   r.rpush(_key(session_id), json.dumps(event))
   r.expire(_key(session_id), 600)  # 10분 TTL
   ```

2. **세션 상태 응답에 포함** (선택사항)
   ```python
   return {
       "answerable": True,
       "session_id": session_id,
       "session_status": "terminated",  # 또는 "active", "clarifying"
       ...
   }
   ```

---

## ✅ 최종 정리

| 항목 | 구현 상태 | 설명 |
|------|----------|------|
| **세션 ID 생성** | 클라이언트 (모바일) | UUID.randomUUID() |
| **세션 유지** | ✅ 구현됨 | Clarify 루프 동안 동일 ID |
| **세션 종료** | ✅ 구현됨 | GPT-4o 답변 완료 시 |
| **Redis 히스토리** | ✅ 구현됨 | session_id 기반 저장/로드 |
| **TTL 자동 만료** | ⚠️ 선택사항 | 현재는 명시적 삭제만 |

---

**결론**: 제공하신 구조 설명이 현재 코드 구현과 100% 일치합니다! ✅

