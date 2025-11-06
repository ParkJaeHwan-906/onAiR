# app/services/generator.py
from __future__ import annotations
from typing import List, Dict, Any
from app.core.config import settings

import json

# ✅ GMS 통합키 하나로 gemini & gpt-4o 둘 다 사용
import google.generativeai as genai
genai.configure(api_key=settings.GMS_API_KEY)


# ==============================
# 🧩 1. Answerability Gate (Gemini Flash)
# ==============================
def llm_self_check(query: str, snippets: List[str]) -> bool:
    """
    Gemini Flash 기반 Self-Check (Clarify 단계)
    """
    prompt = (
        "You are an answerability checker. "
        "If the following snippets are sufficient to answer the query, "
        "respond ONLY with YES, otherwise respond ONLY with NO.\n\n"
        f"Query: {query}\n\nSnippets:\n- " + "\n- ".join(snippets[:5])
    )

    try:
        model = genai.GenerativeModel(settings.GMS_MODEL_GATE)  # gemini-1.5-flash
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip().upper()
        return text.startswith("Y")
    except Exception as e:
        print("[Gemini Flash Self-Check Error]", e)
        return True


# ==============================
# 🧠 2. Final Generator (GPT-4o via GMS)
# ==============================
def llm_generate_answer(query: str, snippets: List[str]) -> str:
    """
    GPT-4o 기반 단계별 점검 가이드 생성기 (GMS 단일키 사용)
    """
    ctx = "\n\n".join(snippets[:5])
    prompt = (
        f"아래 문서를 참고하여 '{query}'에 대한 단계별 점검 절차와 권장 조치 요령을 작성해줘.\n\n"
        f"{ctx}"
    )

    try:
        model = genai.GenerativeModel(settings.GMS_MODEL_GENERATOR)  # gpt-4o
        resp = model.generate_content(prompt)
        return (resp.text or "").strip()
    except Exception as e:
        print("[GPT-4o via GMS Error]", e)
        return synthesize_answer(query, [{"source": {"content": s}} for s in snippets])["answer"]


# ==============================
# 🪄 3. Fallback 합성 (LLM 비활성화시)
# ==============================
def synthesize_answer(query: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    LLM이 없을 때를 대비한 컨텍스트 기반 합성 답변.
    """
    top = sorted(hits, key=lambda x: x.get("rerank_score", 0.0), reverse=True)[:3]
    bullets = []
    for h in top:
        src = h.get("source", {})
        sec = src.get("section", "")
        pages = src.get("pages", [])
        txt = src.get("content", "")
        bullets.append({
            "section": sec,
            "pages": pages,
            "excerpt": (txt[:300] + "…") if len(txt) > 300 else txt
        })

    guidance = []
    for h in top:
        t = h.get("source", {}).get("content", "")
        if "회전 속도" in t or "RPM" in t:
            guidance.append("• 회전속도는 회전계로 측정하고, 모터 명판 RPM과 풀리 직경을 이용해 계산값 검증.")
        if "베어링" in t:
            guidance.append("• 베어링 과열/마모/주유 상태 점검: 과도한 구리스, 이물질, 주유 부족 여부 확인.")
        if "V벨트" in t:
            guidance.append("• V-벨트 장력/슬립 여부 확인: 과도한 장력이나 느슨함 수정.")
        if "전압" in t or "주파수" in t:
            guidance.append("• 전원 전압/주파수 이상, 결상 여부 점검(정격과 일치 확인).")
        if "댐퍼" in t:
            guidance.append("• 댐퍼 개도 및 작동상태 점검(정압/풍량과 연동).")

    guidance = list(dict.fromkeys(guidance))
    return {
        "query": query,
        "answer": "아래 항목을 순서대로 점검하세요:\n" + (
            "\n".join(guidance) if guidance else "• 상위 스니펫을 참고해 점검 절차를 수행하세요."
        ),
        "citations": bullets
    }


# ==============================
# 📊 4. Self-Score (GPT-4o via GMS)
# ==============================
def llm_self_score(query: str, answer: str, snippets: List[str]) -> Dict[str, Any]:
    """
    GPT-4o가 자신의 답변에 대한 품질을 점수로 평가합니다. (GMS 단일키)
    """
    prompt = f"""다음 질문과 답변을 평가해주세요.

질문: {query}

답변:
{answer}

참고 문서:
{chr(10).join(f"- {s[:200]}..." for s in snippets[:3])}

평가 기준:
1. 답변이 질문에 직접적으로 답하는가? (0-1점)
2. 답변이 참고 문서의 정보를 정확히 반영하는가? (0-1점)
3. 답변이 실용적이고 단계별로 명확한가? (0-1점)

다음 JSON 형식으로만 응답하세요:
{{
  "score": 0.0-1.0 사이의 총점,
  "breakdown": {{
    "relevance": 0.0-1.0,
    "accuracy": 0.0-1.0,
    "clarity": 0.0-1.0
  }},
  "comment": "간단한 평가 코멘트"
}}
"""
    try:
        model = genai.GenerativeModel(settings.GMS_MODEL_GENERATOR)
        resp = model.generate_content(prompt)
        return json.loads(resp.text)
    except Exception as e:
        print("[Self-Score Error]", e)
        return {"score": 0.0, "reason": f"평가 중 오류 발생: {e}"}
