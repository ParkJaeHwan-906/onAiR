# 🔍 Clarify 단계 RAG 로직 점검 보고서

## 📋 현재 구현 상태 점검

### ⚠️ 중요: STT 방식 구분

**버퍼링 STT:**
- **용도**: Intent 분류만 (AI_Supporter vs Operator)
- **처리**: `handle_stt_result` 함수에서 `type="final"`이고 `session_id`가 없을 때
- **로직**: Gemini-Flash로 Intent 분류 → 모바일로 전송
- **RAG 연결**: ❌ RAG와 연결되지 않음

**스트리밍 STT:**
- **용도**: Clarify (Gemini-Flash) 및 RAG 기반 최종 답변 생성 (GPT-4o)
- **처리**: `handle_stt_result` 함수에서 `session_id`가 있을 때
- **로직**: `type="final"`이면 `process_clarify_qa_turn` 호출
- **RAG 연결**: ✅ RAG 기반 Evidence Check 및 답변 생성

### ✅ 잘 구현된 부분

#### 1. `process_clarify_qa_turn` 함수 (스트리밍 STT용) - ✅ 개선 완료
**위치:** `ai_server/rag_server/app/sockets/socket_handler.py:424`

**로직 흐름:**
1. ✅ Redis 히스토리 로드 및 컨텍스트 구성
2. ✅ Hybrid Search + Rerank (RAG 기반)
3. ✅ **Evidence Check (RED/YELLOW/GREEN)** - `comprehensive_evidence_check` 사용 (개선됨)
4. ✅ RED/YELLOW → Clarify 질문 생성 (Gemini-Flash) - `make_clarify_prompt` 사용 (개선됨)
5. ✅ GREEN → 최종 답변 생성 (GPT-4o) - `llm_generate_answer` 사용
6. ✅ TTS 생성 및 모바일로 전송

**코드:**
```python
# Evidence Check
need_clarify, evidence_stats = comprehensive_evidence_check(effective_query, used_hits)
gate_decision = evidence_stats.get("gate_decision")

# RED/YELLOW → Clarify 질문 생성
if need_clarify or gate_decision != "GREEN":
    clarified_result = make_clarify_prompt(effective_query, used_hits, evidence_stats)
    # 모바일로 Clarify 턴 전송
    await broadcast_to("mobile", "clarify_turn", {...})

# GREEN → 최종 답변 생성
else:
    answer_text = llm_generate_answer(effective_query, snippets)
    tts_result = text_to_speech(answer_text)
    # 모바일로 최종 답변 전송
    await broadcast_to("mobile", "final_answer", {
        "answer": answer_text,
        "audio_content": tts_result.get("audio_content"),
        "audio_encoding": tts_result.get("audio_encoding"),
        ...
    })
```

#### 2. `process_clarify_turn` 함수 (레거시/모바일 Clarify 응답용)
**위치:** `ai_server/rag_server/app/sockets/socket_handler.py:265`

**용도:**
- 모바일에서 Clarify 응답을 직접 보낼 때 사용
- `clarify_router.py`에서도 사용됨
- **스트리밍 STT와는 별개**로 동작

**로직:**
1. ✅ Redis 히스토리 로드 및 컨텍스트 구성
2. ✅ Hybrid Search + Rerank (RAG 기반)
3. ✅ Evidence Check (RED/YELLOW/GREEN)
4. ✅ RED/YELLOW → Clarify 질문 생성
5. ✅ GREEN → 최종 답변 생성

### ✅ 개선 완료된 부분

#### 1. `process_clarify_qa_turn`에 RAG 기반 Evidence Check 추가 완료 ✅

**개선 전:**
```python
# 단순 LLM 기반 clarify 판단만 사용
clarify_result = clarify_query(user_question)
need_clarify = not clarify_result.get("answerable", True)
```

**개선 후:**
```python
# 1. Hybrid Search + Rerank (RAG 기반)
normalized_query = normalize_query_style(effective_query)
base_hits = hybrid_retrieve(normalized_query, top_k=8)
hits = rerank(normalized_query, base_hits, top_k=6)
used_hits = hits[:5]

# 2. RAG 기반 Evidence Check (RED/YELLOW/GREEN)
need_clarify, evidence_stats = comprehensive_evidence_check(effective_query, used_hits)
gate_decision = evidence_stats.get("gate_decision")

# 3. RED/YELLOW → Clarify 질문 생성 (Gemini-Flash)
if need_clarify or gate_decision != "GREEN":
    clarified_result = make_clarify_prompt(effective_query, used_hits, evidence_stats)
    clarify_question = clarified_result.get("guide", "...")
    # LLM 답변 생성 및 TTS
    ...
```

#### 2. 스트리밍 STT 전용 Clarify/RAG 로직 완성 ✅

**구조:**
- 버퍼링 STT → Intent 분류만 (RAG 미사용)
- 스트리밍 STT → Clarify/RAG 처리 (RAG 기반 Evidence Check 사용)

## 🚀 성능 개선 제안

### 1. RAG 기반 답변 생성 성능 개선

#### 1-1. Hybrid Retrieval 최적화
**현재:**
- Dense (FAISS): BGE-M3 임베딩
- Sparse (Elasticsearch): BM25
- Hybrid Alpha: 0.82 (config.py)

**개선 제안:**
```python
# 동적 Alpha 조정
def adaptive_hybrid_alpha(query: str, query_length: int) -> float:
    """
    쿼리 특성에 따라 Hybrid Alpha를 동적으로 조정
    - 짧은 쿼리: Dense에 더 가중치 (0.85)
    - 긴 쿼리: Sparse에 더 가중치 (0.75)
    - 기술 용어 포함: Dense에 더 가중치 (0.88)
    """
    if query_length < 10:
        return 0.85  # 짧은 쿼리는 Dense에 더 가중치
    elif query_length > 30:
        return 0.75  # 긴 쿼리는 Sparse에 더 가중치
    else:
        return 0.82  # 기본값
```

#### 1-2. Reranking 최적화
**현재:**
- Cross-Encoder: BGE-Reranker-Large
- Rerank Top-K: 6
- Rerank Weight: 0.6

**개선 제안:**
```python
# 쿼리 복잡도에 따른 동적 Top-K 조정
def adaptive_rerank_top_k(query: str, base_hits: List[Dict]) -> int:
    """
    쿼리 복잡도와 검색 결과 품질에 따라 Rerank Top-K 조정
    """
    if len(base_hits) < 5:
        return len(base_hits)  # 결과가 적으면 모두 rerank
    
    # 상위 결과의 점수 분산 확인
    top_scores = [h.get("score", 0) for h in base_hits[:5]]
    score_variance = np.var(top_scores)
    
    if score_variance < 0.1:  # 점수가 비슷하면 더 많이 rerank
        return min(10, len(base_hits))
    else:  # 점수 차이가 크면 상위만 rerank
        return 6
```

#### 1-3. 답변 생성 프롬프트 최적화
**현재:**
```python
prompt = (
    f"아래 문서를 참고하여 '{query}'에 대한 단계별 점검 절차와 권장 조치 요령을 작성해줘.\n\n"
    f"{ctx}"
)
```

**개선 제안:**
```python
def generate_optimized_prompt(query: str, snippets: List[str], evidence_stats: Dict) -> str:
    """
    Evidence 통계를 활용한 최적화된 프롬프트 생성
    """
    # Coverage 정보 추가
    coverage_info = f"검색된 문서는 {evidence_stats.get('coverage_axes', 0)}개 주요 항목을 다룹니다."
    
    # 신뢰도 정보 추가
    confidence_info = f"검색 신뢰도: {evidence_stats.get('confidence', 0):.2f}"
    
    prompt = f"""아래 문서를 참고하여 '{query}'에 대한 단계별 점검 절차와 권장 조치 요령을 작성해주세요.

{coverage_info}
{confidence_info}

**중요:** 
- 문서에 명시된 절차를 정확히 따르세요
- 단계별로 명확하게 구분하여 작성하세요
- 위험 요소가 있다면 반드시 경고하세요

[참고 문서]
{chr(10).join(f"{i+1}. {s[:500]}..." for i, s in enumerate(snippets[:5]))}

[질문]
{query}

[답변 형식]
1. 문제 진단
2. 점검 절차 (단계별)
3. 권장 조치
4. 주의사항 (있는 경우)
"""
    return prompt
```

### 2. Clarify 여부 판단 성능 개선

#### 2-1. Evidence Check 임계값 최적화
**현재 설정 (config.py):**
```python
EVIDENCE_CONFIDENCE_THRESHOLD: float = 0.70
EVIDENCE_COVERAGE_MIN: int = 2
EVIDENCE_CONSISTENCY_THRESHOLD: float = 0.65
EVIDENCE_SEMANTIC_THRESHOLD: float = 0.65
```

**개선 제안:**
```python
# 동적 임계값 조정
def adaptive_evidence_thresholds(query: str, query_type: str) -> Dict[str, float]:
    """
    쿼리 유형에 따라 Evidence 임계값을 동적으로 조정
    """
    base_thresholds = {
        "confidence": 0.70,
        "coverage_min": 2,
        "consistency": 0.65,
        "semantic": 0.65
    }
    
    # 긴급 상황 관련 쿼리는 임계값 완화
    urgent_keywords = ["긴급", "즉시", "위험", "고장", "작동 안함"]
    if any(keyword in query for keyword in urgent_keywords):
        return {
            "confidence": 0.65,  # 완화
            "coverage_min": 1,    # 완화
            "consistency": 0.60,  # 완화
            "semantic": 0.60      # 완화
        }
    
    # 일반 점검 관련 쿼리는 임계값 강화
    maintenance_keywords = ["점검", "유지보수", "정기"]
    if any(keyword in query for keyword in maintenance_keywords):
        return {
            "confidence": 0.75,  # 강화
            "coverage_min": 3,   # 강화
            "consistency": 0.70, # 강화
            "semantic": 0.70    # 강화
        }
    
    return base_thresholds
```

#### 2-2. Clarify 질문 생성 최적화
**현재:**
- `make_clarify_prompt`: Gemini-Flash 사용
- Evidence Trace 기반 구체화 가이드 생성

**개선 제안:**
```python
def generate_contextual_clarify_prompt(
    query: str, 
    hits: List[Dict], 
    evidence_stats: Dict,
    history: List[Dict]
) -> Dict[str, Any]:
    """
    대화 히스토리와 Evidence 통계를 활용한 컨텍스트 기반 Clarify 질문 생성
    """
    # 이전 Clarify 질문 추출 (중복 방지)
    previous_clarify_questions = [
        ev.get("data", {}).get("clarify_guidance", "")
        for ev in history
        if ev.get("type") == "clarify"
    ]
    
    # Missing Info 기반 구체화 방향 제시
    missing_info = evidence_stats.get("missing_info", [])
    weak_areas = [
        area for area in missing_info 
        if area not in previous_clarify_questions
    ]
    
    # Evidence Trace 기반 구체화 가이드
    evidence_trace = evidence_stats.get("evidence_trace", {})
    low_coverage_areas = []
    if evidence_trace.get("coverage_axes", 0) < 3:
        low_coverage_areas.append("관련 부위나 장치를 구체적으로 알려주세요")
    if evidence_trace.get("retrieval_strength", 0) < 0.58:
        low_coverage_areas.append("문제 상황이나 증상을 자세히 설명해주세요")
    
    # 통합 Clarify 가이드 생성
    clarify_guide = "다음 정보를 추가로 알려주시면 더 정확한 답변을 드릴 수 있습니다:\n"
    clarify_guide += "\n".join(f"- {area}" for area in weak_areas + low_coverage_areas)
    
    return {
        "guide": clarify_guide,
        "examples": generate_clarify_examples(query, hits),
        "missing_info": missing_info,
        "evidence_trace": evidence_trace
    }
```

#### 2-3. RED/YELLOW/GREEN 판단 로직 개선
**현재:**
```python
TH_RED = {
    "hit_count": 2,
    "confidence": 0.50,
    "retrieval_strength": 0.50,
    "coverage": 2,
}
TH_GREEN = {
    "confidence": 0.62,
    "retrieval_strength": 0.58,
    "coverage": 3,
    "consistency": 0.60,
    "hit_count": 3,
}
```

**개선 제안:**
```python
def adaptive_gate_thresholds(query: str, query_complexity: str) -> Dict[str, Dict]:
    """
    쿼리 복잡도에 따른 동적 임계값 조정
    """
    if query_complexity == "simple":
        # 간단한 쿼리는 임계값 완화
        return {
            "RED": {
                "hit_count": 1,
                "confidence": 0.45,
                "retrieval_strength": 0.45,
                "coverage": 1,
            },
            "GREEN": {
                "confidence": 0.60,
                "retrieval_strength": 0.55,
                "coverage": 2,
                "consistency": 0.55,
                "hit_count": 2,
            }
        }
    elif query_complexity == "complex":
        # 복잡한 쿼리는 임계값 강화
        return {
            "RED": {
                "hit_count": 3,
                "confidence": 0.55,
                "retrieval_strength": 0.55,
                "coverage": 3,
            },
            "GREEN": {
                "confidence": 0.70,
                "retrieval_strength": 0.65,
                "coverage": 4,
                "consistency": 0.65,
                "hit_count": 4,
            }
        }
    else:
        # 기본값
        return {
            "RED": {
                "hit_count": 2,
                "confidence": 0.50,
                "retrieval_strength": 0.50,
                "coverage": 2,
            },
            "GREEN": {
                "confidence": 0.62,
                "retrieval_strength": 0.58,
                "coverage": 3,
                "consistency": 0.60,
                "hit_count": 3,
            }
        }
```

### 3. TTS 성능 개선

#### 3-1. TTS 캐싱
**개선 제안:**
```python
# Redis에 TTS 결과 캐싱
def get_cached_tts(text: str) -> Optional[Dict]:
    """동일한 텍스트의 TTS 결과를 캐시에서 가져오기"""
    cache_key = f"tts:{hashlib.md5(text.encode()).hexdigest()}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    return None

def cache_tts(text: str, tts_result: Dict):
    """TTS 결과를 캐시에 저장 (24시간 TTL)"""
    cache_key = f"tts:{hashlib.md5(text.encode()).hexdigest()}"
    redis_client.setex(
        cache_key, 
        86400,  # 24시간
        json.dumps(tts_result)
    )
```

#### 3-2. TTS 비동기 처리
**개선 제안:**
```python
# TTS 생성을 비동기 태스크로 처리
async def generate_tts_async(text: str) -> Dict:
    """TTS 생성을 비동기로 처리하여 응답 시간 단축"""
    loop = asyncio.get_event_loop()
    tts_result = await loop.run_in_executor(
        None, 
        text_to_speech, 
        text
    )
    return tts_result
```

## 📊 구현 상태 요약

| 기능 | 버퍼링 STT | 스트리밍 STT (process_clarify_qa_turn) | 상태 |
|------|-----------|--------------------------------------|------|
| **용도** | Intent 분류만 | Clarify/RAG 처리 | ✅ 구분 완료 |
| RAG 기반 검색 | ❌ (미사용) | ✅ | 완료 |
| Evidence Check (RED/YELLOW/GREEN) | ❌ (미사용) | ✅ | **개선 완료** |
| Clarify 질문 생성 (Gemini-Flash) | ❌ (미사용) | ✅ | 완료 |
| 최종 답변 생성 (GPT-4o) | ❌ (미사용) | ✅ | 완료 |
| TTS 생성 | ❌ (미사용) | ✅ | 완료 |
| 모바일 전송 | ✅ (Intent 결과만) | ✅ | 완료 |

## 🎯 우선순위별 개선 사항

### ✅ 완료된 개선 사항
1. **`process_clarify_qa_turn`에 RAG 기반 Evidence Check 추가** ✅
   - `comprehensive_evidence_check` 함수 사용
   - RED/YELLOW/GREEN 판단 로직 통합
   - `make_clarify_prompt`로 RAG 기반 Clarify 질문 생성

### 🟡 중간 우선순위
2. **동적 임계값 조정 로직 추가**
   - 쿼리 유형에 따른 Evidence 임계값 조정
   - 쿼리 복잡도에 따른 Gate 임계값 조정

3. **답변 생성 프롬프트 최적화**
   - Evidence 통계를 활용한 컨텍스트 추가
   - 단계별 답변 형식 강화

### 🟢 낮은 우선순위
4. **TTS 캐싱 및 비동기 처리**
   - Redis 캐싱으로 중복 TTS 생성 방지
   - 비동기 처리로 응답 시간 단축

5. **Hybrid Retrieval 최적화**
   - 동적 Alpha 조정
   - 쿼리 특성에 따른 가중치 조정

## 📝 다음 단계

1. ✅ `process_clarify_qa_turn`에 RAG 기반 Evidence Check 추가 (완료)
2. ⏳ 동적 임계값 조정 로직 구현 (선택사항)
3. ⏳ 답변 생성 프롬프트 최적화 (선택사항)
4. ⏳ TTS 캐싱 구현 (선택사항)
5. ⏳ 성능 테스트 및 벤치마크 (권장)

## 📌 핵심 정리

### STT 방식별 역할

**버퍼링 STT (3~5초 음성):**
- ✅ Intent 분류만 (AI_Supporter vs Operator)
- ❌ RAG와 연결되지 않음
- ❌ Clarify/RAG 처리에 사용되지 않음

**스트리밍 STT (실시간):**
- ✅ Clarify (Gemini-Flash) 처리
- ✅ RAG 기반 최종 답변 생성 (GPT-4o)
- ✅ Evidence Check (RED/YELLOW/GREEN) 사용

