from fastapi import APIRouter, Query
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.llm_service import clarify_query
import os

router = APIRouter()

MIN_HYBRID = float(os.getenv("GATE_MIN_HYBRID", 0.2))
MIN_RERANK = float(os.getenv("GATE_MIN_RERANK", 1.0))

@router.post("/chat")
def chat(query: str):
    # 1️⃣ Hybrid Retrieval
    cands = hybrid_retrieve(query)
    if not cands:
        return {
            "answerable": False,
            "clarify": "관련 문서를 찾을 수 없습니다. 질문을 조금 더 구체적으로 해주세요.",
            "debug": {"gate": {"avg_hybrid": 0, "avg_rerank": 0, "passed": False}, "hits": 0}
        }

    # 2️⃣ Rerank
    hits = rerank(query, cands)
    if not hits:
        return {
            "answerable": False,
            "clarify": "관련 문서를 찾을 수 없습니다. 질문을 조금 더 구체적으로 해주세요.",
            "debug": {"gate": {"avg_hybrid": 0, "avg_rerank": 0, "passed": False}, "hits": 0}
        }

    # 3️⃣ Self-check Gate 계산
    avg_hybrid = sum(h.get("hybrid_score", 0) for h in hits) / len(hits)
    avg_rerank = sum(h.get("rerank_score", 0) for h in hits) / len(hits)
    gate_passed = (avg_hybrid > MIN_HYBRID) and (avg_rerank > MIN_RERANK)

    # 4️⃣ Gemini Flash Clarify 판정
    clarify_result = clarify_query(query)
    llm_answerable = clarify_result.get("answerable", True)

    # 5️⃣ Clarify 결정 (둘 중 하나라도 False 면 Clarify 모드)
    if not (gate_passed and llm_answerable):
        return {
            "answerable": False,
            "clarify": clarify_result.get(
                "clarify",
                "질문이 다소 포괄적입니다. 예: 송풍기 / 댐퍼 / 코일 / 필터 중 어떤 부품인가요?"
            ),
            "debug": {
                "gate": {
                    "avg_hybrid": round(avg_hybrid, 2),
                    "avg_rerank": round(avg_rerank, 2),
                    "passed": gate_passed
                },
                "llm": clarify_result,
                "hits": len(hits)
            }
        }

    # 6️⃣ 정상 통과 → 임시 응답
    answer = "임시 응답입니다. 관련 문서 근거:\n" + "\n".join(
        [f"- [{h['source'].get('section')}] p{h['source'].get('pages')} / score={round(h['rerank_score'],3)}"
         for h in hits]
    )

    return {
        "answerable": True,
        "query": query,
        "answer": answer,
        "contexts": hits,
        "debug": {
            "gate": {
                "avg_hybrid": round(avg_hybrid, 2),
                "avg_rerank": round(avg_rerank, 2),
                "passed": gate_passed
            },
            "llm": clarify_result,
            "hits": len(hits)
        }
    }
