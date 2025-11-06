# app/services/answerability.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple
import re, json
import numpy as np
from app.core.config import settings
from app.core.model_loader import embed_texts, KNOWN_SUBJECTS
import google.generativeai as genai

genai.configure(api_key=settings.GMS_API_KEY)


def _tokenize(q: str) -> List[str]:
    return [t for t in re.split(r"\s+", q.strip()) if t]


def heuristic_gate(query: str, hits: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
    """
    휴리스틱 게이트: RAG 결과 품질이 기준 이하일 때 Clarify 단계로 전환
    (기본 검증 - 빠른 필터링용)
    """
    tokens = _tokenize(query)
    long_enough = len(tokens) >= settings.ANSW_MIN_QUERY_LEN

    n = len(hits)
    enough_docs = n >= settings.ANSW_MIN_DOCS
    if n == 0:
        return False, {"reason": "no_hits"}

    avg_hybrid = sum(h["hybrid_score"] for h in hits) / n
    top_rerank = max(h.get("rerank_score", 0.0) for h in hits)

    strong_hybrid = avg_hybrid >= settings.ANSW_MIN_HYBRID
    strong_rerank = top_rerank >= settings.ANSW_MIN_RERANK

    answerable = enough_docs and (strong_hybrid or strong_rerank) and long_enough
    return answerable, {
        "enough_docs": enough_docs,
        "avg_hybrid": round(avg_hybrid, 4),
        "top_rerank": round(top_rerank, 4),
        "long_enough": long_enough,
    }


# ====== V2 Clarify Gate (RED/YELLOW/GREEN) ======

def comprehensive_evidence_check(query: str, hits: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
    """
    Clarify 게이트 (RED/YELLOW/GREEN).
    반환: (need_clarify, stats)
    - need_clarify 는 오직 RED일 때만 True
    - stats.gate_decision = "RED" | "YELLOW" | "GREEN"
    - stats.failed_clauses / rule_name / thresholds 포함
    """
    # STEP 0: RAG subject validation (주어가 임베딩 데이터에 존재하는지)
    subj_gate = subject_gate_check(query)
    if subj_gate is not None:
        return True, subj_gate

    if not hits:
        return True, {
            "gate_decision": "RED",
            "reason": "no_hits",
            "hit_count": 0,
            "failed_clauses": ["no_hits"],
            "evidence_sufficiency": False
        }

    # 1) evidence & semantic
    evidence_ok, evidence_stats = evaluate_evidence_sufficiency(
        hits,
        confidence_threshold=settings.EVIDENCE_CONFIDENCE_THRESHOLD,
        coverage_min=settings.EVIDENCE_COVERAGE_MIN,
        consistency_threshold=settings.EVIDENCE_CONSISTENCY_THRESHOLD
    )
    semantic_ok, semantic_stats = evaluate_semantic_evidence(
        query, hits, semantic_threshold=settings.EVIDENCE_SEMANTIC_THRESHOLD
    )

    # 2) primitives
    hit_count = len(hits)
    confidence = evidence_stats.get("confidence", 0.0)
    coverage_axes = evidence_stats.get("coverage_axes", 0)
    consistency_score = evidence_stats.get("consistency_score", 0.0)
    retrieval_strength = semantic_stats.get("retrieval_strength", 0.0)
    semantic_score = semantic_stats.get("semantic_score", 0.0)

    # 3) thresholds
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

    failed_clauses: List[str] = []

    # RED check
    red_hits = []
    if hit_count < TH_RED["hit_count"]:
        failed_clauses.append("hit_count")
        red_hits.append("hit_count")
    if confidence < TH_RED["confidence"]:
        failed_clauses.append("confidence(red)")
        red_hits.append("confidence")
    if retrieval_strength < TH_RED["retrieval_strength"]:
        failed_clauses.append("retrieval_strength(red)")
        red_hits.append("retrieval_strength")
    if coverage_axes < TH_RED["coverage"]:
        failed_clauses.append("coverage(red)")
        red_hits.append("coverage")

    if red_hits:
        need_clarify = True
        gate = "RED"
        rule = "RED_basic"
    else:
        strong_conf_rule = (confidence >= 0.70 and coverage_axes >= 3 and hit_count >= 3)
        green_core = (
            confidence >= TH_GREEN["confidence"] and
            retrieval_strength >= TH_GREEN["retrieval_strength"] and
            coverage_axes >= TH_GREEN["coverage"] and
            consistency_score >= TH_GREEN["consistency"] and
            hit_count >= TH_GREEN["hit_count"]
        )

        if strong_conf_rule or green_core:
            need_clarify = False
            gate = "GREEN"
            rule = "strong_conf_rule" if strong_conf_rule else "GREEN_core"
        else:
            # YELLOW: 답변은 가능, 보조 질문 제안
            need_clarify = False
            gate = "YELLOW"
            rule = "YELLOW_borderline"

    # evidence trace
    evidence_trace = {
        "semantic_score": round(semantic_score, 3),
        "retrieval_confidence": round(confidence, 3),
        "coverage_axes": coverage_axes,
        "consistency_score": round(consistency_score, 3),
        "retrieval_strength": round(retrieval_strength, 4),
        "hit_sections": [h.get("source", {}).get("section", "") for h in hits[:3]],
    }
    evidence_sources = [
        {
            "section": h.get("source", {}).get("section", ""),
            "pages": h.get("source", {}).get("pages", []),
            "score": round(h.get("rerank_score", 0.0), 3),
        } for h in hits[:3]
    ]

    # need_clarify일 때만 missing 추출
    missing_info: List[str] = []
    clarify_guidance = ""
    if need_clarify and gate == "RED":
        missing_info = extract_missing_slots(query, hits)
        clarify_guidance = make_clarify_guidance(missing_info)

    stats = {
        **evidence_stats,
        **semantic_stats,
        "hit_count": hit_count,
        "is_question_specific": not need_clarify,
        "need_clarify": need_clarify,
        "gate_decision": gate,
        "gate_rule": rule,
        "failed_clauses": failed_clauses,
        "evidence_trace": evidence_trace,
        "evidence_sources": evidence_sources,
        "missing_info": missing_info,
        "clarify_guidance": clarify_guidance,
        "telemetry": {
            "hit_count": hit_count,
            "confidence": round(confidence, 4),
            "coverage_axes": coverage_axes,
            "consistency_score": round(consistency_score, 4),
            "retrieval_strength": round(retrieval_strength, 4),
            "semantic_score": round(semantic_score, 4),
            "evidence_sufficiency": evidence_ok,
            "semantic_sufficiency": semantic_ok,
            "thresholds": {
                "RED": TH_RED,
                "GREEN": TH_GREEN,
                "strong_conf_rule": "conf>=0.70 & coverage>=3 & hits>=3",
            },
        },
    }

    return need_clarify, stats


def evaluate_axes(hits: List[Dict[str, Any]]) -> int:
    """
    근거 커버리지 평가: 검색된 문서들이 다양한 정보 축(원인, 조치, 진단 등)을 포함하는지 평가
    """
    if not hits:
        return 0
    
    # 섹션 기반 축 분류 (공조기 매뉴얼 기준)
    axes_keywords = {
        "원인": ["원인", "원인분석", "발생원인", "고장원인", "문제원인"],
        "조치": ["조치", "대응", "수리", "점검", "교체", "조정", "보수"],
        "진단": ["진단", "확인", "점검", "검사", "측정", "체크"],
        "증상": ["증상", "현상", "표시", "이상", "불량"],
        "예방": ["예방", "방지", "주의", "관리", "유지보수"]
    }
    
    found_axes = set()
    for h in hits[:5]:  # 상위 5개만 검사
        content = h.get("source", {}).get("content", "").lower()
        section = h.get("source", {}).get("section", "").lower()
        text = content + " " + section
        
        for axis_name, keywords in axes_keywords.items():
            if any(kw in text for kw in keywords):
                found_axes.add(axis_name)
    
    return len(found_axes)


def evaluate_consistency(hits: List[Dict[str, Any]]) -> float:
    """
    일관성 점수: 검색된 문서들 간 내용의 충돌 여부 평가 (0.0 ~ 1.0)
    높을수록 일관적 (충돌 없음)
    """
    if len(hits) < 2:
        return 1.0  # 문서가 1개면 일관성 점수 최대
    
    # 상위 3개 문서 간 유사도 계산 (의미적 일관성)
    contents = [h.get("source", {}).get("content", "")[:500] for h in hits[:3]]
    if len(contents) < 2:
        return 1.0
    
    try:
        # 임베딩 벡터로 유사도 계산
        embeddings = embed_texts(contents, is_query=False)
        
        # 평균 코사인 유사도
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = float(np.dot(embeddings[i], embeddings[j]))  # normalize되어 있으므로 dot product가 cosine similarity
                similarities.append(max(0.0, sim))  # 음수면 0으로
        
        consistency = np.mean(similarities) if similarities else 0.5
        return float(consistency)
    except Exception as e:
        print(f"[Consistency Evaluation Error] {e}")
        return 0.7  # 기본값


def evaluate_evidence_sufficiency(
    hits: List[Dict[str, Any]], 
    confidence_threshold: float = None,
    coverage_min: int = None,
    consistency_threshold: float = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    1️⃣ Evidence Sufficiency Check
    
    기본값은 settings에서 가져옴 (구버전 기본값 사용 방지)
    
    Returns:
        (is_sufficient, stats)
    """
    if confidence_threshold is None:
        confidence_threshold = settings.EVIDENCE_CONFIDENCE_THRESHOLD
    if coverage_min is None:
        coverage_min = settings.EVIDENCE_COVERAGE_MIN
    if consistency_threshold is None:
        consistency_threshold = settings.EVIDENCE_CONSISTENCY_THRESHOLD
    if not hits:
        return False, {
            "reason": "no_hits",
            "confidence": 0.0,
            "coverage_axes": 0,
            "consistency_score": 0.0
        }
    
    confidence = float(hits[0].get("rerank_score", 0.0))
    coverage_axes = evaluate_axes(hits)
    consistency_score = evaluate_consistency(hits)
    
    evidence_sufficiency = (
        confidence >= confidence_threshold and
        coverage_axes >= coverage_min and
        consistency_score >= consistency_threshold
    )
    
    return evidence_sufficiency, {
        "confidence": round(confidence, 4),
        "coverage_axes": coverage_axes,
        "consistency_score": round(consistency_score, 4),
        "evidence_sufficiency": evidence_sufficiency
    }


def normalize_query_style(query: str) -> str:
    """
    문체 정규화: retrieval 전에 적용하여 검색 품질 향상
    """
    # 공조기 매뉴얼 문체로 정규화
    normalized = query
    replacements = {
        "않습니다": "안 됩니다",
        "않아": "안 돼요",
        "되지 않": "안 되",
        "않고": "안 하고",
        "않는": "안 되는",
        "않으면": "안 되면",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized


def evaluate_semantic_evidence(
    query: str,
    hits: List[Dict[str, Any]],
    semantic_threshold: float = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    2️⃣ Semantic + Evidence 결합
    
    Top3 결합 텍스트로 semantic score 계산 (단일 문단보다 정확)
    
    Returns:
        (is_specific, stats)
    """
    if semantic_threshold is None:
        semantic_threshold = settings.EVIDENCE_SEMANTIC_THRESHOLD
    
    if not hits:
        return False, {
            "semantic_score": 0.0,
            "retrieval_strength": 0.0,
            "is_question_specific": False
        }
    
    best_hit = hits[0]
    confidence = float(best_hit.get("rerank_score", 0.0))
    
    # Top3 결합 텍스트로 semantic score 계산
    try:
        # 상위 3개 문서의 텍스트 결합
        top_passages = [h.get("source", {}).get("content", "")[:500] for h in hits[:3]]
        combined_text = " ".join(top_passages)
        
        q_emb = embed_texts([query], is_query=True)
        p_emb = embed_texts([combined_text], is_query=False)
        
        if q_emb.ndim == 1:
            q_emb = q_emb.reshape(1, -1)
        if p_emb.ndim == 1:
            p_emb = p_emb.reshape(1, -1)
        
        semantic_score = float(np.dot(q_emb[0], p_emb[0]))  # normalize되어 있으므로 cosine similarity
        retrieval_strength = (semantic_score + confidence) / 2
        
        is_question_specific = retrieval_strength >= semantic_threshold
        
        return is_question_specific, {
            "semantic_score": round(semantic_score, 4),
            "confidence": round(confidence, 4),
            "retrieval_strength": round(retrieval_strength, 4),
            "is_question_specific": is_question_specific,
            "semantic_method": "top3_combined"
        }
    except Exception as e:
        print(f"[Semantic Evaluation Error] {e}")
        return False, {
            "semantic_score": 0.0,
            "retrieval_strength": 0.0,
            "is_question_specific": False,
            "error": str(e)
        }


def extract_missing_slots(query: str, hits: List[Dict[str, Any]]) -> List[str]:
    """
    질문 내에서 누락된 핵심 슬롯 추정 (부품명, 증상, 운전상태 등)
    
    Returns:
        missing_info: 누락된 정보 슬롯 리스트
    """
    q_lower = query.lower()
    missing = []
    
    # 1. 부품명 체크
    equipment_keywords = [
        "모터", "댐퍼", "펌프", "필터", "밸브", "코일", 
        "송풍기", "냉각기", "가열기", "베어링", "벨트",
        "드레인", "엘리미네이터", "팬", "콤프레셔"
    ]
    if not any(kw in q_lower for kw in equipment_keywords):
        missing.append("부품명")
    
    # 2. 증상/현상 체크
    symptom_keywords = [
        "회전", "작동", "정지", "열림", "닫힘", "막힘",
        "소음", "진동", "과열", "누수", "누설", "트립",
        "불량", "고장", "이상", "문제", "증상"
    ]
    if not any(kw in q_lower for kw in symptom_keywords):
        missing.append("증상")
    
    # 3. 운전상태 체크
    operation_keywords = [
        "차단기", "전원", "비상정지", "퓨즈", "스위치",
        "on", "off", "켜", "꺼", "정상", "트립"
    ]
    if not any(kw in q_lower for kw in operation_keywords):
        # 증상이 있는데 운전상태가 없으면 추가
        if any(kw in q_lower for kw in symptom_keywords):
            missing.append("운전상태")
    
    # 4. 상황/조건 체크 (선택적)
    condition_keywords = [
        "때", "중", "상태", "조건", "온도", "압력", 
        "속도", "시간", "횟수"
    ]
    # 너무 짧거나 맥락이 부족한 경우
    if len(query.split()) < 5 and not any(kw in q_lower for kw in condition_keywords):
        if not missing:  # 다른 슬롯이 이미 missing이면 추가 안 함
            missing.append("상황설명")
    
    return missing


def make_clarify_guidance(missing_info: List[str]) -> str:
    """
    누락된 정보를 기반으로 맞춤형 Clarify 안내 생성
    
    Args:
        missing_info: 누락된 정보 슬롯 리스트
        
    Returns:
        clarify_guidance: 사용자에게 보여줄 안내 문구
    """
    if not missing_info:
        return "질문이 충분히 구체화되어 있습니다."
    
    guide_parts = []
    
    if "부품명" in missing_info:
        guide_parts.append("어떤 부품(예: 송풍기, 모터, 댐퍼, 필터 등)의 문제인지 알려주세요.")
    
    if "증상" in missing_info:
        guide_parts.append("문제가 어떤 현상으로 나타나는지 구체적으로 작성해주세요.")
    
    if "운전상태" in missing_info:
        guide_parts.append("전원, 차단기, 비상정지 스위치, 보호계전기 상태를 포함해주세요.")
    
    if "상황설명" in missing_info:
        guide_parts.append("언제, 어떤 상황에서 발생했는지 추가 정보를 알려주세요.")
    
    return " ".join(guide_parts)


def make_clarify_options(missing_info: List[str]) -> Dict[str, Any]:
    """
    누락된 정보 유형에 따라 사용자에게 제시할 질문(ask)과 선택지(options)를 생성.
    """
    if not missing_info:
        return {"ask": "추가로 알려주실 정보가 있나요?", "options": ["없음", "기타: 직접 입력"]}

    # 우선순위: 부품명 > 운전상태 > 증상
    if "부품명" in missing_info:
        return {
            "ask": "어떤 부품이 작동하지 않나요?",
            "options": [
                "송풍기 모터",
                "배수펌프",
                "압축기",
                "댐퍼",
                "필터",
                "기타: 직접 입력",
            ],
        }
    if "운전상태" in missing_info:
        return {
            "ask": "전원/차단기/비상정지 스위치 상태는 어떠한가요?",
            "options": [
                "차단기 ON, 비상정지 해제",
                "차단기 OFF",
                "보호계전기 TRIP",
                "확인 불가",
                "기타",
            ],
        }
    if "증상" in missing_info:
        return {
            "ask": "문제가 어떤 현상으로 나타나나요?",
            "options": [
                "회전 불량/정지",
                "소음/진동",
                "과열",
                "막힘/누수",
                "기타",
            ],
        }

    return {"ask": "조금만 더 구체화해 주세요.", "options": ["예시 보기", "기타: 직접 입력"]}


def has_known_subject(query: str) -> bool:
    q = query.lower().replace(" ", "")
    for subj in KNOWN_SUBJECTS:
        if subj and subj in q:
            return True
    return False


def subject_gate_check(query: str) -> Dict[str, Any] | None:
    if not has_known_subject(query):
        return {
            "need_clarify": True,
            "gate_decision": "RED",
            "gate_rule": "RED_subject_not_in_RAG",
            "reason": "질문에 포함된 장비/부품명이 RAG 데이터 내에서 확인되지 않습니다.",
            "clarify_guidance": "어떤 장비나 부품에 대한 문제인지 명확히 말씀해주세요. 예: 송풍기, 댐퍼, 필터 등.",
        }
    return None


def make_clarify_prompt(
    query: str, 
    hits: List[Dict[str, Any]], 
    evidence_stats: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Gemini Flash 기반 RAG-aware Clarify Guide (Evidence Trace + Redis History 포함)
    검색된 문서 일부를 참고하여 왜 모호한지 / 어떤 방향으로 구체화해야 할지 / 예시를 생성
    이전 대화 맥락을 반영하여 점진적 구체화 유도
    """
    # Evidence Trace에서 정보 추출
    evidence_trace = evidence_stats.get("evidence_trace", {}) if evidence_stats else {}
    missing_info = evidence_stats.get("missing_info", []) if evidence_stats else []
    clarify_guidance = evidence_stats.get("clarify_guidance", "") if evidence_stats else ""
    history = evidence_stats.get("history", []) if evidence_stats else []
    
    # 🔹 RAG 문서의 대표 섹션 및 내용 추출
    top_sections = list({h.get("source", {}).get("section", "") for h in hits[:5]})
    context_snippets = "\n\n".join(
        h.get("source", {}).get("content", "")[:300] for h in hits[:3]
    )

    # 이전 대화 맥락 구성 (Redis 히스토리)
    conversation_context = ""
    if history:
        conv_lines = []
        for event in history[-6:]:  # 최근 6개 이벤트만
            role = event.get("role", "")
            event_type = event.get("type", "")
            data = event.get("data", {})
            if role == "user" and event_type == "query":
                conv_lines.append(f"사용자: {data.get('query', '')}")
            elif role == "system" and event_type == "evidence":
                prev_missing = data.get("missing_info", [])
                if prev_missing:
                    conv_lines.append(f"시스템: 누락된 정보 - {', '.join(prev_missing)}")
        if conv_lines:
            conversation_context = f"""
[이전 대화 맥락]
{chr(10).join(conv_lines)}

⚠️ 중요: 위 대화를 참고하여, 이전에 누락되었다고 언급한 정보가 이번 질문에 포함되었는지 확인하고,
여전히 부족한 부분만 추가로 요청해야 합니다.
"""

    # Evidence Trace 기반으로 더 구체적인 프롬프트 구성
    evidence_summary = f"""
[검색 품질 지표]
- 의미 유사도: {evidence_trace.get('semantic_score', 0):.3f}
- 검색 신뢰도: {evidence_trace.get('retrieval_confidence', 0):.3f}
- 정보 커버리지: {evidence_trace.get('coverage_axes', 0)}개 축
- 일관성 점수: {evidence_trace.get('consistency_score', 0):.3f}
- 누락된 정보: {', '.join(missing_info) if missing_info else '없음'}

⚠️ 판단 기준: 이 RAG 근거로 최종 답변을 생성할 수 있을 만큼 충분히 구체화되었는지 평가하세요.
검색 신뢰도가 0.62 이상이고, retrieval_strength가 0.58 이상이며, coverage가 3 이상이면 구체화 충분합니다.
"""

    prompt = f"""
너는 공조기 및 설비 유지보수 분야의 질문 분석 전문가야.
아래는 사용자가 한 질문과, RAG로 검색된 문서 일부, 그리고 검색 품질 지표야.

{conversation_context}

이 정보들을 참고해서 아래 항목을 JSON 형식으로 작성해줘:

1️⃣ 왜 질문이 모호한지 (빠진 정보 기반)
2️⃣ 어떤 방향으로 구체화해야 하는지 (부위, 현상, 상황)
3️⃣ 문서 내용을 기반으로 구체화 예시 3개

JSON 형식:
{{
  "reason": "...",
  "guide": "...",
  "examples": ["...", "...", "..."]
}}

[사용자 질문]
{query}

{evidence_summary}

[관련 문서 섹션]
{", ".join(top_sections)}

[문서 내용 일부]
{context_snippets}
"""

    try:
        model = genai.GenerativeModel(settings.GMS_MODEL_GATE)
        resp = model.generate_content(prompt)
        text = resp.text or ""
        
        # JSON 블록 제거
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        
        result = json.loads(text)
        
        # Evidence Trace 구조 통합
        result["need_clarify"] = True
        result["original_query"] = query
        result["clarifier_model"] = settings.GMS_MODEL_GATE
        result["used_sections"] = top_sections
        result["evidence_trace"] = evidence_trace
        result["missing_info"] = missing_info
        result["evidence_sources"] = evidence_stats.get("evidence_sources", []) if evidence_stats else []
        
        # Gemini가 생성한 guide가 있으면 사용, 없으면 기존 guidance 사용
        if not result.get("guide") and clarify_guidance:
            result["guide"] = clarify_guidance
        
        return result
    except Exception as e:
        print("[Clarify Generation Error]", e)
        # Fallback: Evidence Trace 기반 기본 응답
        return {
            "need_clarify": True,
            "reason": "질문이 다소 광범위하거나 문서 내 직접적인 근거가 부족합니다.",
            "guide": clarify_guidance or "RAG 문서 내 유사 섹션을 참고해, 특정 부위나 현상을 명시해주세요.",
            "examples": [
                "송풍기 모터가 회전하지 않습니다.",
                "댐퍼가 열리지 않습니다.",
                "필터가 막혀 풍량이 줄어요."
            ],
            "original_query": query,
            "clarifier_model": settings.GMS_MODEL_GATE,
            "used_sections": top_sections,
            "evidence_trace": evidence_trace,
            "missing_info": missing_info,
            "evidence_sources": evidence_stats.get("evidence_sources", []) if evidence_stats else []
        }
