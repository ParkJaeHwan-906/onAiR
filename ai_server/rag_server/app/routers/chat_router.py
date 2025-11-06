from __future__ import annotations
from fastapi import APIRouter, Query, Body
from typing import Any, Dict

from app.core.config import settings
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.answerability import (
    make_clarify_prompt,
    comprehensive_evidence_check,
    normalize_query_style
)
from app.services.generator import llm_self_check, llm_generate_answer, synthesize_answer, llm_self_score
from app.services import memory

router = APIRouter(prefix="/rag", tags=["RAG: Chat"])

from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None

@router.post("/chat")
def rag_chat(request: ChatRequest = Body(...)) -> Dict[str, Any]:
    query = request.query
    session_id = request.session_id

    """
    ✅ RAG Chat 엔드포인트
    - Clarify 단계: Gemini Flash
    - Generate 단계: GPT-4o
    """

    # -------------------------
    # 1️⃣ 세션 히스토리 반영 + 문체 정규화 (retrieval 전에 적용)
    # -------------------------
    history_context = ""
    if session_id:
        prev = memory.get_history(session_id)
        # 최근 사용자 query 2개만 요약 결합
        user_lines = []
        for ev in reversed(prev):
            if ev.get("role") == "user" and ev.get("type") == "query":
                user_lines.append(ev.get("data", {}).get("query", ""))
            if len(user_lines) >= 2:
                break
        if user_lines:
            history_context = " \n".join(reversed(user_lines))

    effective_query = f"{history_context} \n{query}" if history_context else query
    normalized_query = normalize_query_style(effective_query)

    # 현재 발화를 메모리에 즉시 저장 (모든 경우)
    if session_id:
        memory.append_event(session_id, {
            "role": "user",
            "type": "query",
            "data": {"query": query}
        })
    
    # -------------------------
    # 2️⃣ Hybrid Retrieve + Rerank
    # -------------------------
    base_hits = hybrid_retrieve(normalized_query, top_k=settings.TOP_K)
    hits = rerank(normalized_query, base_hits, top_k=settings.RERANK_TOP_K)
    used_hits = hits[:5]

    if not hits:
        return {
            "answerable": False,
            "reason": "관련 문서를 찾을 수 없습니다.",
            "clarify": {"reason": "검색 결과가 없습니다. 질문을 다시 작성해주세요."}
        }

    # -------------------------
    # 3️⃣ Evidence Sufficiency Check + Semantic 결합
    # -------------------------
    need_clarify, evidence_stats = comprehensive_evidence_check(effective_query, used_hits)
    gate_decision = evidence_stats.get("gate_decision")
    # 정책: GREEN이 아니면 무조건 Clarify 흐름으로 유도 (YELLOW 포함)
    force_clarify = gate_decision != "GREEN"
    
    clarifier_model = settings.GMS_MODEL_GATE  # gemini-1.5-flash
    generator_model = settings.GMS_MODEL_GENERATOR  # gpt-4o
    
    # -------------------------
    # 3️⃣ Clarify 분기 (Evidence Trace + Redis 메모리)
    # -------------------------
    if need_clarify or force_clarify:
        # Evidence Stats에 이미 evidence_trace, missing_info, clarify_guidance 포함됨
        # 이전 히스토리 로드 및 추가 기록
        if session_id:
            history = memory.get_history(session_id)
            evidence_stats["history"] = history
            memory.append_event(session_id, {
                "role": "user",
                "type": "query",
                "data": {"query": query}
            })
            memory.append_event(session_id, {
                "role": "system",
                "type": "evidence",
                "data": evidence_stats
            })

        clarified_result = make_clarify_prompt(effective_query, used_hits, evidence_stats)
        
        print(f"[Clarify Triggered] Missing Info: {evidence_stats.get('missing_info', [])}")
        print(f"[Clarify Triggered] Evidence Trace: {evidence_stats.get('evidence_trace', {})}")

        return {
            "answerable": False,
            "need_clarify": True,
            "reason": clarified_result.get("reason", "질문이 구체적이지 않거나 문서 연결성이 낮습니다."),
            "clarifier_model": clarifier_model,
            "generator_model": generator_model,
            "evidence_trace": evidence_stats.get("evidence_trace", {}),
            "missing_info": evidence_stats.get("missing_info", []),
            "clarify_guidance": evidence_stats.get("clarify_guidance", clarified_result.get("guide", "")),
            "ask": (evidence_stats.get("clarify_ask_options", {}) or {}).get("ask"),
            "options": (evidence_stats.get("clarify_ask_options", {}) or {}).get("options", []),
            "evidence_sources": evidence_stats.get("evidence_sources", []),
            "rag_stats": {
                "retrieval_strength": (evidence_stats.get("evidence_trace", {}) or {}).get("retrieval_strength"),
                "evidence_sufficiency": evidence_stats.get("evidence_sufficiency"),
            },
            "source_sections": (evidence_stats.get("evidence_trace", {}) or {}).get("hit_sections", []),
            "clarified_query": clarified_result,
            "debug": {
                "gate_decision": evidence_stats.get("gate_decision"),
                "gate_rule": evidence_stats.get("gate_rule"),
                "failed_clauses": evidence_stats.get("failed_clauses", []),
                "hits": len(used_hits),
                **evidence_stats.get("telemetry", {})
            },
        }

    # -------------------------
    # 4️⃣ Final Answer (GPT-4o) - Evidence가 충분한 경우 (GREEN)
    # -------------------------
    snippets = [h["source"]["content"] for h in used_hits]
    answer_text = llm_generate_answer(effective_query, snippets)
    print(f"[Generate Model] → {generator_model}")
    print(f"[Evidence Sufficient] Stats: {evidence_stats}")

    # 성공적으로 답변 생성되면 세션 히스토리 종료/정리
    if session_id:
        memory.append_event(session_id, {
            "role": "assistant",
            "type": "answer",
            "data": {"answer": answer_text}
        })
        # 정책: 완료 시 세션 초기화 (원하면 주석 처리)
        memory.clear_history(session_id)

    # -------------------------
    # 5️⃣ Self-Score (optional)
    # -------------------------
    score_result = None
    if settings.LLM_PROVIDER == "openai":
        score_result = llm_self_score(query, answer_text, snippets)

    # -------------------------
    # 6️⃣ 최종 결과 구성
    # -------------------------
    result = {
        "answerable": True,
        "result": {
            "query": query,
            "clarifier_model": clarifier_model,
            "generator_model": generator_model,
            "answer": answer_text,
            "borderline": (evidence_stats.get("gate_decision") == "YELLOW"),
            "followup_prompt": (
                "추가로 알려주실 정보가 있나요? (예: 전원/차단기 상태, 보호계전기 트립 여부, 특정 부품명)"
                if evidence_stats.get("gate_decision") == "YELLOW" else None
            ),
            "rag_stats": {
                "retrieval_strength": (evidence_stats.get("evidence_trace", {}) or {}).get("retrieval_strength"),
                "evidence_sufficiency": evidence_stats.get("evidence_sufficiency"),
            },
            "source_sections": (evidence_stats.get("evidence_trace", {}) or {}).get("hit_sections", []),
            "citations": [
                {
                    "section": h["source"]["section"],
                    "pages": h["source"]["pages"],
                }
                for h in used_hits[:3]
            ],
        },
        "debug": {
            "gate_decision": evidence_stats.get("gate_decision"),
            "gate_rule": evidence_stats.get("gate_rule"),
            "failed_clauses": evidence_stats.get("failed_clauses", []),
            "hits": len(used_hits),
            **evidence_stats
        },
    }

    if score_result:
        result["result"]["self_score"] = score_result

    return result
