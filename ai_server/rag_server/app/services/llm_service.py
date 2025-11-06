import json
from app.core.config import settings

try:
    import google.generativeai as genai
    genai_available = True
except Exception:
    genai = None
    genai_available = False

# ✅ Gemini 설정 (config.py의 GEMINI_API_KEY 사용)
if genai_available and settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model_clarify = genai.GenerativeModel("gemini-1.5-flash")
else:
    model_clarify = None


def clarify_query(query: str) -> dict:
    """
    Gemini 1.5 Flash에게 Clarify 여부를 묻는 함수.
    질문이 포괄적이면 answerable=False와 함께 구체화 프롬프트를 반환.
    """
    if not genai_available or not model_clarify:
        # Gemini가 없으면 기본적으로 통과
        return {
            "answerable": True,
            "clarify": "질문이 구체적입니다."
        }
    
    prompt = f"""
당신은 기술 매뉴얼 QA 시스템의 Clarification 모듈입니다.
다음 질문이 구체적입니까, 아니면 너무 포괄적입니까?

질문: "{query}"

출력 형식(JSON strict):
{{
  "answerable": true|false,
  "clarify": "필요시 사용자에게 보낼 구체화 질문 또는 안내문"
}}
"""

    try:
        response = model_clarify.generate_content(prompt)
        text = response.text.strip()

        # ```json ``` 블록 형식 대응
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()

        result = json.loads(text)
    except Exception as e:
        result = {
            "answerable": True,
            "clarify": f"Clarify 판정 중 오류 발생: {e}"
        }

    return result
