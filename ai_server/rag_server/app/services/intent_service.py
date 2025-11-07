import json
from app.core.config import settings

try:
    import google.generativeai as genai
    genai_available = True
except Exception:
    genai = None
    genai_available = False

# ✅ Gemini 설정 (config.py의 GMS_API_KEY 사용)
if genai_available and settings.GMS_API_KEY:
    genai.configure(api_key=settings.GMS_API_KEY)
    model_intent = genai.GenerativeModel("gemini-1.5-flash")
else:
    model_intent = None


# clarify_query는 llm_service.py에 있으므로 여기서는 제거


def classify_intent(text: str) -> dict:
    """
    Gemini-Flash를 사용하여 Intent 분류 수행
    
    사용자의 말을 분석하여 OPERATOR 통신 연결이 필요한지, 
    AI_SUPPORTER가 처리할 수 있는 질문인지 판단합니다.
    
    Args:
        text: 버퍼링 STT로 변환된 사용자 입력 텍스트
        
    Returns:
        {
            "intent": "OPERATOR" | "AI_SUPPORTER",
            "confidence": 0.0~1.0,
            "reasoning": "판단 근거"
        }
    """
    if not genai_available or not model_intent:
        # Gemini가 없으면 기본적으로 AI_SUPPORTER로 분류
        return {
            "intent": "AI_SUPPORTER",
            "confidence": 0.5,
            "reasoning": "Gemini 모델을 사용할 수 없어 기본값으로 분류했습니다."
        }
    
    prompt = f"""당신은 사용자 의도를 분류하는 시스템입니다.

사용자의 말을 분석하여 다음 두 가지 중 하나로 분류하세요:

1. **OPERATOR**: 사람 오퍼레이터와의 통신 연결이 필요한 경우
   - 예: "통신연결이 필요해", "사람 불러줘", "오퍼레이터 연결해줘", "직원 불러줘", "담당자 연결", "상담원 연결", "전화 연결해줘" 등
   - 사람과 직접 통화하거나 상담이 필요한 요청

2. **AI_SUPPORTER**: AI 서포터가 처리할 수 있는 질문이나 요청
   - 예: "AI 도움이 필요해", "이거 어떻게 하는지 알려줘", "설명해줘", "질문이 있어", "방법 알려줘" 등
   - AI가 답변하거나 안내할 수 있는 일반적인 질문

사용자 입력: "{text}"

**중요 규칙:**
- 반드시 "OPERATOR" 또는 "AI_SUPPORTER" 중 하나만 반환하세요.
- 다른 값이나 설명을 추가하지 마세요.
- JSON 형식으로만 응답하세요.

출력 형식 (JSON strict):
{{
  "intent": "OPERATOR" 또는 "AI_SUPPORTER",
  "confidence": 0.0~1.0 사이의 숫자,
  "reasoning": "판단 근거를 한 문장으로 설명"
}}
"""

    try:
        response = model_intent.generate_content(prompt)
        text_response = response.text.strip()

        # ```json ``` 블록 형식 대응
        if "```" in text_response:
            text_response = text_response.split("```")[1].replace("json", "").strip()

        result = json.loads(text_response)
        
        # Intent 값 검증 및 정규화
        intent = result.get("intent", "").upper()
        if intent not in ["OPERATOR", "AI_SUPPORTER"]:
            # 잘못된 값이면 기본값으로 처리
            result["intent"] = "AI_SUPPORTER"
            result["confidence"] = 0.5
            result["reasoning"] = f"잘못된 Intent 값 '{intent}'를 받아 기본값으로 처리했습니다."
        
        return result
        
    except json.JSONDecodeError as e:
        # JSON 파싱 실패 시 텍스트에서 직접 추출 시도
        text_response = response.text.strip().upper()
        if "OPERATOR" in text_response:
            return {
                "intent": "OPERATOR",
                "confidence": 0.7,
                "reasoning": "JSON 파싱 실패로 텍스트에서 OPERATOR를 감지했습니다."
            }
        else:
            return {
                "intent": "AI_SUPPORTER",
                "confidence": 0.7,
                "reasoning": "JSON 파싱 실패로 기본값으로 처리했습니다."
            }
    except Exception as e:
        return {
            "intent": "AI_SUPPORTER",
            "confidence": 0.5,
            "reasoning": f"Intent 분류 중 오류 발생: {e}"
        }

