import json
from app.core.config import settings
from app.services.gms_client import call_gemini_via_gms

# ✅ GMS API 키 확인
gms_api_key = settings.GMS_API_KEY if settings.GMS_API_KEY else None


def clarify_query(query: str) -> dict:
    """
    Gemini 1.5 Flash에게 Clarify 여부를 묻는 함수.
    질문이 포괄적이면 answerable=False와 함께 구체화 프롬프트를 반환.
    """
    if not gms_api_key:
        # GMS API 키가 없으면 기본적으로 통과
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
        print(f"🔵 [Clarify] Gemini-Flash API 호출 시작: '{query[:50]}...'")
        # GMS API를 통해 Gemini 호출
        text = call_gemini_via_gms(
            model="gemini-1.5-flash",
            prompt=prompt,
            api_key=gms_api_key
        ).strip()
        print(f"✅ [Clarify] Gemini-Flash API 호출 성공 (응답 길이: {len(text)} bytes)")

        # ```json ``` 블록 형식 대응
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()

        result = json.loads(text)
        print(f"✅ [Clarify] Clarify 판정 결과: answerable={result.get('answerable')}")
    except Exception as e:
        print(f"❌ [Clarify] Gemini-Flash API 호출 실패: {type(e).__name__}: {str(e)[:200]}")
        result = {
            "answerable": True,
            "clarify": f"Clarify 판정 중 오류 발생: {e}"
        }

    return result
