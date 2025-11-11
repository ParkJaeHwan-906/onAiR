# app/services/generator.py
from __future__ import annotations
from typing import List, Dict, Any
from app.core.config import settings

import json

# ✅ GMS 통합키 하나로 gemini & gpt-4o 둘 다 사용
import google.generativeai as genai

# API 키 설정 (None 체크)
if settings.GMS_API_KEY:
    genai.configure(api_key=settings.GMS_API_KEY)
    print(f"✅ [Generator] GMS_API_KEY 설정 완료: {settings.GMS_API_KEY[:10]}...")
else:
    print("⚠️ [Generator] GMS_API_KEY가 설정되지 않았습니다.")


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
        print(f"🔵 [Self-Check] Gemini-Flash API 호출 시작 (모델: {settings.GMS_MODEL_GATE})")
        model = genai.GenerativeModel(settings.GMS_MODEL_GATE)  # gemini-1.5-flash
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip().upper()
        result = text.startswith("Y")
        print(f"✅ [Self-Check] Gemini-Flash API 호출 성공: {result} (응답: {text[:50]})")
        return result
    except Exception as e:
        print(f"❌ [Self-Check] Gemini-Flash API 호출 실패: {type(e).__name__}: {str(e)[:200]}")
        return True


# ==============================
# 🧠 2. Final Generator (GPT-4o via GMS) - Structured Output + TTS 친화적
# ==============================
def format_for_tts(text: str) -> str:
    """
    TTS 친화적 형식으로 변환
    - 숫자를 말로 변환
    - 리스트를 자연스러운 문장으로 변환
    - 기호를 말로 변환
    """
    import re
    
    # 숫자를 말로 변환 (1 → 첫 번째, 2 → 두 번째)
    number_map = {
        "1": "첫 번째", "2": "두 번째", "3": "세 번째", "4": "네 번째",
        "5": "다섯 번째", "6": "여섯 번째", "7": "일곱 번째", "8": "여덟 번째",
        "9": "아홉 번째", "10": "열 번째"
    }
    
    # "1단계" → "첫 번째 단계"
    for num, word in number_map.items():
        text = re.sub(rf"{num}단계", f"{word} 단계", text)
        text = re.sub(rf"{num}\.", f"{word}로, ", text)
    
    # "•" → "그리고"
    text = re.sub(r"•\s*", "그리고 ", text)
    
    # ":" → "는 다음과 같습니다"
    text = re.sub(r":\s*", "는 다음과 같습니다. ", text)
    
    # 줄바꿈을 자연스러운 연결로
    text = re.sub(r"\n+", ". ", text)
    
    return text.strip()

def llm_generate_answer(query: str, snippets: List[str], hits: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    GPT-4o 기반 구조화된 답변 생성 (JSON Schema) + TTS 친화적 변환
    """
    ctx = "\n\n".join(snippets[:5])
    
    # 출처 정보 추출
    citations = []
    if hits:
        for h in hits[:3]:
            src = h.get("source", {})
            citations.append({
                "section": src.get("section", ""),
                "pages": src.get("pages", ""),
                "excerpt": src.get("content", "")[:200]
            })
    
    prompt = f"""
아래 문서를 참고하여 '{query}'에 대한 진단 및 조치 가이드를 JSON 형식으로 작성하세요.

[참고 문서]
{ctx}

⚠️ 중요: 이 답변은 TTS(음성 합성)로 재생됩니다. 따라서:
- 짧고 명확한 문장 사용
- 숫자는 말로 표현 (예: "1단계" → "첫 번째 단계")
- 리스트는 자연스러운 문장으로 연결
- 전문 용어는 쉬운 말로 설명
- 안전 주의사항은 명확히 강조

[출력 형식 - 반드시 JSON만 출력]
{{
  "summary": "문제 요약 (1-2문장, TTS 친화적)",
  "possible_causes": [
    "원인 1 (간단명료하게)",
    "원인 2",
    "원인 3"
  ],
  "diagnosis_steps": [
    {{
      "step": 1,
      "action": "점검 항목 (TTS 친화적 표현)",
      "method": "점검 방법 (구체적으로)",
      "expected_result": "정상 상태 설명"
    }},
    ...
  ],
  "recommended_actions": [
    {{
      "priority": "high" | "medium" | "low",
      "action": "조치 내용 (TTS 친화적 표현)",
      "safety_note": "안전 주의사항 (있을 경우, 명확하게)"
    }},
    ...
  ],
  "safety_warnings": [
    "안전 주의사항 1 (명확하고 강조)",
    "안전 주의사항 2"
  ],
  "related_sections": [
    "관련 섹션명 1",
    "관련 섹션명 2"
  ]
}}

⚠️ 중요:
- diagnosis_steps는 순서대로 실행 가능한 단계별 점검 절차
- recommended_actions는 priority 순으로 정렬
- safety_warnings는 반드시 포함 (없으면 빈 배열)
- 모든 내용은 참고 문서에 근거해야 함
- TTS로 재생되므로 자연스럽고 이해하기 쉬운 표현 사용
"""

    try:
        print(f"🔵 [Generator] GPT-4o API 호출 시작 (모델: {settings.GMS_MODEL_GENERATOR})")
        model = genai.GenerativeModel(settings.GMS_MODEL_GENERATOR)  # gpt-4o
        resp = model.generate_content(prompt)
        text = resp.text or ""
        print(f"✅ [Generator] GPT-4o API 호출 성공 (응답 길이: {len(text)} bytes)")
        
        # JSON 블록 제거
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        
        result = json.loads(text)
        print(f"✅ [Generator] 답변 생성 완료: summary={result.get('summary', '')[:50]}...")
        
        # TTS 친화적 텍스트 생성
        tts_text_parts = []
        
        # 요약
        if result.get("summary"):
            tts_text_parts.append(result["summary"])
        
        # 가능한 원인
        if result.get("possible_causes"):
            tts_text_parts.append("가능한 원인은 다음과 같습니다.")
            for i, cause in enumerate(result["possible_causes"][:3], 1):
                tts_text_parts.append(f"{i}번째로, {cause}")
        
        # 진단 단계
        if result.get("diagnosis_steps"):
            tts_text_parts.append("다음과 같이 점검하세요.")
            step_number_map = {
                1: "첫 번째", 2: "두 번째", 3: "세 번째", 4: "네 번째",
                5: "다섯 번째", 6: "여섯 번째", 7: "일곱 번째", 8: "여덟 번째",
                9: "아홉 번째", 10: "열 번째"
            }
            for step in result["diagnosis_steps"]:
                step_num = step.get("step", 1)
                action = step.get("action", "")
                method = step.get("method", "")
                expected = step.get("expected_result", "")
                
                step_word = step_number_map.get(step_num, f"{step_num}번째")
                step_text = f"{step_word} 단계로, {action}"
                if method:
                    step_text += f" {method}"
                if expected:
                    step_text += f" 정상 상태는 {expected}입니다"
                tts_text_parts.append(step_text)
        
        # 권장 조치
        if result.get("recommended_actions"):
            tts_text_parts.append("권장 조치는 다음과 같습니다.")
            for action_item in result["recommended_actions"]:
                action = action_item.get("action", "")
                safety = action_item.get("safety_note", "")
                priority = action_item.get("priority", "medium")
                
                priority_text = "우선적으로" if priority == "high" else ""
                action_text = f"{priority_text} {action}"
                if safety:
                    action_text += f" 단, 주의하실 점은 {safety}입니다"
                tts_text_parts.append(action_text)
        
        # 안전 주의사항
        if result.get("safety_warnings"):
            tts_text_parts.append("중요한 안전 주의사항입니다.")
            for warning in result["safety_warnings"]:
                tts_text_parts.append(warning)
        
        # TTS 친화적 텍스트 생성
        tts_text = ". ".join(tts_text_parts)
        tts_text = format_for_tts(tts_text)
        
        # 구조화된 답변에 TTS 텍스트 추가
        result["tts_text"] = tts_text
        result["citations"] = citations
        result["query"] = query
        
        return result
    except Exception as e:
        print(f"❌ [Generator] GPT-4o API 호출 실패: {type(e).__name__}: {str(e)[:200]}")
        # Fallback: 기존 방식
        fallback_answer = synthesize_answer(query, hits or [{"source": {"content": s}} for s in snippets])["answer"]
        tts_text = format_for_tts(fallback_answer)
        return {
            "summary": f"'{query}'에 대한 점검 및 조치 가이드",
            "answer": fallback_answer,
            "tts_text": tts_text,
            "citations": citations,
            "query": query
        }


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
        print(f"🔵 [Self-Score] GPT-4o API 호출 시작 (모델: {settings.GMS_MODEL_GENERATOR})")
        model = genai.GenerativeModel(settings.GMS_MODEL_GENERATOR)
        resp = model.generate_content(prompt)
        result = json.loads(resp.text)
        print(f"✅ [Self-Score] GPT-4o API 호출 성공: score={result.get('score', 0.0):.2f}")
        return result
    except Exception as e:
        print(f"❌ [Self-Score] GPT-4o API 호출 실패: {type(e).__name__}: {str(e)[:200]}")
        return {"score": 0.0, "reason": f"평가 중 오류 발생: {e}"}
