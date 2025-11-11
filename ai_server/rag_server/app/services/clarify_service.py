# app/services/clarify_service.py
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.llm_service import cosine_similarity
from app.services.answerability import evaluate_axes, evaluate_consistency

class ClarifyService:
    """
    질문이 충분히 구체화되었는지 (즉, Retrieval 근거가 답변 생성에 충분한지)
    판단하는 Clarifier 게이트 서비스.
    """

    def __init__(self,
                 confidence_threshold=0.68,
                 sim_threshold=0.7):
        self.confidence_threshold = confidence_threshold
        self.sim_threshold = sim_threshold

    def assess_specificity(self, query: str):
        # 1️⃣ Retrieval
        hits = hybrid_retrieve(query)
        reranked = rerank(query, hits)

        if not reranked:
            return {
                "need_clarify": True,
                "reason": "관련 근거를 찾지 못했습니다.",
                "telemetry": {"hit_count": 0}
            }

        # 2️⃣ Evidence Sufficiency
        coverage_axes = evaluate_axes(reranked)
        consistency_score = evaluate_consistency(reranked)
        confidence = reranked[0]["score"]

        # 문체 정규화 (형태소 차이로 인한 임베딩 mismatch 완화)
        query = query.replace("않습니다", "안 됩니다").replace("않아", "안 돼요")

        # 3️⃣ Semantic Sufficiency
        # top3 문단 기준으로 의미 유사도 평균화
        top_texts = " ".join([h["text"] for h in reranked[:3]])
        semantic_score = cosine_similarity(query, top_texts)

        # semantic + retrieval confidence 평균
        retrieval_strength = (semantic_score + confidence) / 2

        # 4️⃣ 완화된 threshold 기준으로 sufficiency 판단
        evidence_sufficiency = (
            confidence >= 0.68 and
            coverage_axes >= 2 and
            consistency_score >= 0.6
        )

        is_question_specific = (
            retrieval_strength >= 0.7 and evidence_sufficiency
        )

        # 5️⃣ Clarify 여부 결정
        need_clarify = not is_question_specific

        return {
            "need_clarify": need_clarify,
            "semantic_score": semantic_score,
            "confidence": confidence,
            "coverage_axes": coverage_axes,
            "consistency_score": consistency_score,
            "reason": None if not need_clarify else "근거가 불충분하거나 문서 연결성이 낮습니다.",
            "telemetry": {
                "retrieval_strength": retrieval_strength,
                "evidence_sufficiency": evidence_sufficiency
            }
        }
