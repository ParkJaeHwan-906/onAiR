"""
GMS API 클라이언트
GMS 프록시 서버를 통해 Gemini 및 GPT-4o 모델 호출
"""
import json
import requests
from typing import Dict, Any, Optional
from app.core.config import settings

GMS_BASE_URL = "https://gms.ssafy.io/gmsapi"


def call_gemini_via_gms(
    model: str,
    prompt: str,
    api_key: str
) -> str:
    """
    GMS 프록시를 통해 Gemini 모델 호출
    
    Args:
        model: 모델 이름 (예: "gemini-1.5-flash", "gemini-2.0-flash")
        prompt: 입력 프롬프트
        api_key: GMS API 키
        
    Returns:
        모델 응답 텍스트
    """
    # GMS Gemini 엔드포인트 구성
    # 예: https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=$GMS_KEY
    endpoint = f"{GMS_BASE_URL}/generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    # 요청 본문 구성
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    # Query String으로 API 키 전달
    params = {"key": api_key}
    
    try:
        print(f"🔵 [GMS Client] Gemini API 호출 시작: {endpoint}")
        print(f"   모델: {model}, 프롬프트 길이: {len(prompt)} bytes")
        
        response = requests.post(
            endpoint,
            params=params,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30.0
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Gemini 응답 파싱
        if "candidates" in result and len(result["candidates"]) > 0:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            print(f"✅ [GMS Client] Gemini API 호출 성공 (응답 길이: {len(text)} bytes)")
            return text
        else:
            raise ValueError("Gemini 응답에 candidates가 없습니다.")
            
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        print(f"❌ [GMS Client] Gemini API HTTP 오류: {error_msg}")
        raise Exception(error_msg) from e
    except Exception as e:
        print(f"❌ [GMS Client] Gemini API 호출 실패: {type(e).__name__}: {str(e)[:200]}")
        raise


def call_openai_via_gms(
    model: str,
    prompt: str,
    api_key: str,
    system_prompt: Optional[str] = None
) -> str:
    """
    GMS 프록시를 통해 OpenAI 모델 호출 (GPT-4o 등)
    
    Args:
        model: 모델 이름 (예: "gpt-4o", "gpt-4.1")
        prompt: 입력 프롬프트
        api_key: GMS API 키
        system_prompt: 시스템 프롬프트 (선택)
        
    Returns:
        모델 응답 텍스트
    """
    # GMS OpenAI 엔드포인트 구성
    # 예: https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions
    endpoint = f"{GMS_BASE_URL}/api.openai.com/v1/chat/completions"
    
    # 요청 본문 구성
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages
    }
    
    # Header에 Bearer Token으로 API 키 전달
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        print(f"🔵 [GMS Client] OpenAI API 호출 시작: {endpoint}")
        print(f"   모델: {model}, 프롬프트 길이: {len(prompt)} bytes")
        print(f"   시스템 프롬프트: {'있음' if system_prompt else '없음'}")
        print(f"   메시지 개수: {len(messages)}")
        
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=60.0
        )
        
        # HTTP 상태 코드 확인
        print(f"📡 [GMS Client] HTTP 응답 상태: {response.status_code}")
        
        # 응답 본문 확인 (에러 디버깅용)
        response_text = response.text
        if response.status_code != 200:
            print(f"❌ [GMS Client] HTTP 오류 응답 본문: {response_text[:500]}")
        
        response.raise_for_status()
        
        result = response.json()
        
        # 응답 구조 확인 (디버깅용)
        print(f"📦 [GMS Client] 응답 구조 확인:")
        print(f"   - 'choices' 키 존재: {'choices' in result}")
        if "choices" in result:
            print(f"   - choices 개수: {len(result['choices'])}")
            if len(result["choices"]) > 0:
                choice = result["choices"][0]
                print(f"   - choice 구조: {list(choice.keys())}")
                if "message" in choice:
                    print(f"   - message 구조: {list(choice['message'].keys())}")
        
        # OpenAI 응답 파싱
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            text = message.get("content", "")
            
            if not text:
                print(f"⚠️ [GMS Client] 응답에 content가 없습니다. 전체 응답: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
                raise ValueError("OpenAI 응답에 content가 없습니다.")
            
            print(f"✅ [GMS Client] OpenAI API 호출 성공 (응답 길이: {len(text)} bytes)")
            print(f"   응답 미리보기: {text[:100]}...")
            return text
        else:
            print(f"❌ [GMS Client] 응답에 choices가 없습니다. 전체 응답: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
            raise ValueError("OpenAI 응답에 choices가 없습니다.")
            
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:500]}"
        print(f"❌ [GMS Client] OpenAI API HTTP 오류: {error_msg}")
        print(f"   요청 URL: {endpoint}")
        print(f"   요청 헤더: {headers}")
        print(f"   요청 본문 (일부): {json.dumps(payload, ensure_ascii=False)[:500]}")
        raise Exception(error_msg) from e
    except Exception as e:
        print(f"❌ [GMS Client] OpenAI API 호출 실패: {type(e).__name__}: {str(e)[:500]}")
        import traceback
        print(f"   상세 오류:\n{traceback.format_exc()}")
        raise

