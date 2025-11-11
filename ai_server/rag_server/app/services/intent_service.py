import json
from app.core.config import settings
from app.services.gms_client import call_gemini_via_gms

# ✅ GMS API 키 확인
if settings.GMS_API_KEY:
    api_key_preview = settings.GMS_API_KEY[:10] + "..." if len(settings.GMS_API_KEY) > 10 else settings.GMS_API_KEY
    print(f"✅ [Intent Service] GMS_API_KEY 로드됨: {api_key_preview} (길이: {len(settings.GMS_API_KEY)})")
    gms_api_key = settings.GMS_API_KEY
else:
    print("⚠️ [Intent Service] GMS_API_KEY가 설정되지 않았습니다. (None 또는 빈 문자열)")
    print("   환경 변수 GMS_API_KEY를 확인하세요.")
    gms_api_key = None


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
    if not gms_api_key:
        # GMS API 키가 없으면 기본적으로 AI_SUPPORTER로 분류
        return {
            "intent": "AI_SUPPORTER",
            "confidence": 0.5,
            "reasoning": "GMS API 키가 설정되지 않아 기본값으로 분류했습니다."
        }
    
    prompt = f"""당신은 사용자 의도를 분류하는 시스템입니다.

사용자의 말을 분석하여 다음 두 가지 중 하나로 분류하세요:

1. **OPERATOR**: 사람 오퍼레이터와의 통신 연결이 필요한 경우
   - 키워드: "오퍼레이터", "통신", "연결", "사람", "직원", "담당자", "상담원", "전화", "통화"
   - 예시: 
     * "오퍼레이터 통신", "오퍼레이터 연결", "오퍼레이터 불러줘"
     * "통신 연결", "통신 연결해줘", "통신이 필요해"
     * "사람 불러줘", "직원 불러줘", "담당자 연결", "상담원 연결"
     * "전화 연결해줘", "통화 연결", "사람과 통화"
   - 사람과 직접 통화하거나 상담이 필요한 요청

2. **AI_SUPPORTER**: AI 서포터가 처리할 수 있는 질문이나 요청
   - 키워드: "질문", "알려줘", "설명", "방법", "어떻게", "도움", "AI"
   - 예시: 
     * "AI 도움이 필요해", "이거 어떻게 하는지 알려줘"
     * "설명해줘", "질문이 있어", "방법 알려줘"
     * "이거 뭐야", "어떻게 해야 해", "가르쳐줘"
   - AI가 답변하거나 안내할 수 있는 일반적인 질문

사용자 입력: "{text}"

**중요 규칙:**
- "오퍼레이터", "통신", "연결" 등의 키워드가 포함되면 OPERATOR로 분류하세요.
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
        print(f"🔵 [Intent 분류] Gemini-Flash API 호출 시작: '{text[:50]}...'")
        # GMS API를 통해 Gemini 호출
        text_response = call_gemini_via_gms(
            model="gemini-1.5-flash",
            prompt=prompt,
            api_key=gms_api_key
        ).strip()
        print(f"✅ [Intent 분류] Gemini-Flash API 호출 성공 (응답 길이: {len(text_response)} bytes)")

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
        
        print(f"✅ [Intent 분류] Intent 분류 결과: {result.get('intent')} (신뢰도: {result.get('confidence', 0.5):.2f})")
        return result
        
    except json.JSONDecodeError as e:
        # JSON 파싱 실패 시 텍스트에서 직접 추출 시도
        text_response = text_response.strip().upper()
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
        error_msg = str(e)
        print(f"❌ [Intent 분류] 예외 발생: {type(e).__name__}: {error_msg[:200]}")
        return _fallback_classify_intent(text, error_msg)


def _fallback_classify_intent(text: str, error_msg: str) -> dict:
    """
    API 키 오류 등으로 Gemini 호출이 실패했을 때 텍스트 기반 키워드 매칭으로 Intent 분류
    
    Args:
        text: 사용자 입력 텍스트
        error_msg: 발생한 오류 메시지
        
    Returns:
        Intent 분류 결과 딕셔너리
    """
    # OPERATOR 키워드 목록 (한글은 대소문자 구분 없음)
    operator_keywords = ["오퍼레이터", "통신", "연결", "사람", "직원", "담당자", "상담원", "전화", "통화", "연락"]
    
    # 텍스트에서 키워드 검색 (대소문자 구분 없이)
    text_lower = text.lower()  # 한글은 영향 없지만 일관성을 위해
    
    # 키워드 매칭 (한글 키워드는 원본 그대로 사용)
    found_keywords = [kw for kw in operator_keywords if kw in text]
    
    if found_keywords:
        print(f"✅ [Fallback 분류] OPERATOR 키워드 감지: {found_keywords}")
        return {
            "intent": "OPERATOR",
            "confidence": 0.7,
            "reasoning": f"API 오류로 텍스트 기반 분류 수행: OPERATOR 키워드 감지 ({', '.join(found_keywords)})"
        }
    else:
        print(f"⚠️ [Fallback 분류] OPERATOR 키워드 없음 → AI_SUPPORTER로 분류")
        return {
            "intent": "AI_SUPPORTER",
            "confidence": 0.6,
            "reasoning": f"API 오류로 텍스트 기반 분류 수행: OPERATOR 키워드 없음 (원본 오류: {error_msg[:100]})"
        }

