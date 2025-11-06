# app/services/chat_service.py
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.answerability import heuristic_gate, make_clarify_prompt
from app.services.generator import llm_generate_answer
from app.core.config import settings


def rag_chat(query: str) -> Dict[str, Any]:
    """
    전체 RAG + Clarify + Answer 파이프라인
    """
    # 1️⃣ RAG 검색
    hits = hybrid_retrieve(query)
    reranked_hits = rerank(query, hits)

    # 2️⃣ 휴리스틱 판단
    ok, stats = heuristic_gate(query, reranked_hits)

    # 3️⃣ Clarify 필요 시
    if not ok:
        clarify = make_clarify_prompt(query, reranked_hits)
        clarify["rag_stats"] = stats
        return clarify

    # 4️⃣ 답변 생성
    snippets = [h["source"]["content"] for h in reranked_hits[:5]]
    answer = llm_generate_answer(query, snippets)

    return {
        "need_clarify": False,
        "answer": answer,
        "clarifier_model": settings.GMS_MODEL_GATE,
        "generator_model": settings.GMS_MODEL_GENERATOR,
        "rag_stats": stats,
        "source_sections": [h["source"]["section"] for h in reranked_hits[:5] if "source" in h]
    }
