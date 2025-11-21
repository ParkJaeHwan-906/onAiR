# app/services/generator.py
from __future__ import annotations
from typing import List, Dict, Any
from app.core.config import settings
from app.services.gms_client import call_gemini_via_gms, call_openai_via_gms

import json

# ✅ GMS API 키 확인
if settings.GMS_API_KEY:
    key_preview = settings.GMS_API_KEY[:10] + "..." if len(settings.GMS_API_KEY) > 10 else settings.GMS_API_KEY
    print(f"✅ [Generator] GMS_API_KEY 설정 완료: {key_preview} (길이: {len(settings.GMS_API_KEY)})")
    gms_api_key = settings.GMS_API_KEY
else:
    print("⚠️ [Generator] GMS_API_KEY가 설정되지 않았습니다.")
    print("   환경 변수 GMS_API_KEY를 확인하세요.")
    gms_api_key = None


# ==============================
# 🧠 Final Generator (GPT-4o via GMS) - Structured Output + TTS 친화적
# ==============================

def generate_cv_detection_notification(device_type: str, anomalies: Dict[str, Dict[str, Any]]) -> str:
    """
    CV 탐지 성공 시 간단한 알림 메시지 생성
    "어떤 모듈에서 발생한 어떤 오류가 탐지되었습니다." 형식
    """
    if not gms_api_key:
        # Fallback: 간단한 메시지
        detected_items = []
        for module_name, module_res in anomalies.items():
            if isinstance(module_res, dict) and module_res.get("status") == "anomaly":
                detail = module_res.get("detail")
                if detail:
                    detected_items.append(f"{module_name}의 {detail}")
                else:
                    detected_items.append(module_name)
        
        if detected_items:
            return f"{device_type}에서 {', '.join(detected_items)} 오류가 탐지되었습니다."
        return f"{device_type}에서 이상이 탐지되었습니다."
    
    # GPT-4o로 자연스러운 알림 메시지 생성
    detected_items = []
    for module_name, module_res in anomalies.items():
        if isinstance(module_res, dict) and module_res.get("status") == "anomaly":
            detail = module_res.get("detail")
            if detail:
                detected_items.append(f"{module_name}.{detail}")
            else:
                detected_items.append(module_name)
    
    if not detected_items:
        return f"{device_type}에서 이상이 탐지되었습니다."
    
    prompt = f"""다음 정보를 바탕으로 간단하고 명확한 탐지 알림 메시지를 생성하세요.

장비: {device_type}
탐지된 오류: {', '.join(detected_items)}

요구사항:
- "어떤 모듈에서 발생한 어떤 오류가 탐지되었습니다." 형식
- 자연스럽고 명확한 문장
- TTS로 재생되므로 짧고 명확하게
- 추가 설명 없이 알림만

예시:
- "AHU에서 게이지의 압력 과다 오류가 탐지되었습니다."
- "AHU에서 게이지의 압력 과다와 팬 벨트의 벨트 슬립 오류가 탐지되었습니다."

답변은 알림 메시지만 출력하세요."""
    
    try:
        text = call_openai_via_gms(
            model=settings.GMS_MODEL_GENERATOR,
            prompt=prompt,
            api_key=gms_api_key
        ).strip()
        return text
    except Exception as e:
        print(f"⚠️ CV 탐지 알림 메시지 생성 실패: {e}")
        # Fallback
        if len(detected_items) == 1:
            return f"{device_type}에서 {detected_items[0]} 오류가 탐지되었습니다."
        else:
            return f"{device_type}에서 {len(detected_items)}개의 오류가 탐지되었습니다."

def _generate_fallback_answer(
    error_code: str,
    snippets: List[str],
    citations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    GPT-4o 호출 실패 시 RAG snippets 기반 간단한 Fallback 답변 생성
    """
    if not snippets:
        return None
    
    # snippets에서 핵심 정보 추출
    combined_text = "\n\n".join(snippets[:3])
    
    # 간단한 원인 추출 (키워드 기반)
    causes = []
    if "필터" in combined_text or "차압" in combined_text:
        causes.append("필터 막힘 또는 차압 증가")
    if "댐퍼" in combined_text or "개도" in combined_text:
        causes.append("댐퍼 개도 상태 이상")
    if "인버터" in combined_text or "주파수" in combined_text:
        causes.append("인버터 출력 주파수 이상")
    if "압력" in combined_text or "압력계" in combined_text:
        causes.append("압력계 측정 오차 가능성")
    if not causes:
        causes.append("설비 점검이 필요합니다")
    
    # 간단한 조치 추출
    actions = []
    if "필터" in combined_text:
        actions.append("프리필터 및 헤파필터 차압 측정 후 기준 초과 시 교체")
    if "댐퍼" in combined_text:
        actions.append("송풍기 댐퍼 개도 상태 확인 및 70% 이하로 조정")
    if "인버터" in combined_text:
        actions.append("팬 인버터 출력 주파수 확인 (정상 범위: 40~60Hz)")
    if "밸브" in combined_text:
        actions.append("코일 입출구 배관의 밸브 개도, 손상, 막힘 여부 확인")
    if not actions:
        actions.append("설비 점검표에 따라 순차적으로 점검하세요")
    
    # 간단한 주의사항
    warnings = []
    if "압력" in combined_text:
        warnings.append("압력이 1.5bar 이상 지속 시 팬 과부하 위험이 있습니다")
    if "온도" in combined_text:
        warnings.append("고온 상태에서 작업 시 화상 주의하세요")
    if not warnings:
        warnings.append("안전장비를 착용하고 점검하세요")
    
    # 마크다운 생성
    causes_markdown = "## 🟥 원인\n\n" + "\n".join([f"- {c}" for c in causes])
    actions_markdown = "## 🛠 조치\n\n" + "\n".join([f"{i+1}. {a}" for i, a in enumerate(actions)])
    warnings_markdown = "## ⚠ 주의사항\n\n" + "\n".join([f"- {w}" for w in warnings])
    
    markdown_text = f"# 🔧 {error_code}\n\n{causes_markdown}\n\n{actions_markdown}\n\n{warnings_markdown}"
    
    # TTS 텍스트 생성
    tts_text = f"{error_code}에 대한 정비 가이드입니다. 원인은 {', '.join(causes[:3])} 등이 있습니다. 조치 단계는 {', '.join(actions[:3])} 입니다. 주의사항으로는 {', '.join(warnings[:2])}가 있습니다."
    
    return {
        "error_code": error_code,
        "markdown_text": markdown_text,
        "possible_causes": causes,
        "recommended_actions": [{"action": a, "priority": "medium"} for a in actions],
        "safety_warnings": warnings,
        "possible_causes_markdown": causes_markdown,
        "recommended_actions_markdown": actions_markdown,
        "safety_warnings_markdown": warnings_markdown,
        "possible_causes_audio": None,  # Fallback에서는 TTS 생성 안 함
        "possible_causes_audio_encoding": None,
        "recommended_actions_audio": None,
        "recommended_actions_audio_encoding": None,
        "safety_warnings_audio": None,
        "safety_warnings_audio_encoding": None,
        "tts_text": tts_text,
        "query": error_code,
        "citations": citations
    }

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

def llm_generate_answer(
    query: str,
    snippets: List[str],
    error_code: str = None,
    hits: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    GPT-4o 기반 구조화된 정비 가이드 출력
    - Markdown 구조 강제
    - error_code 기반 출력
    - RAG snippets 기반 생성
    - TTS friendly text 생성
    """
    # ----------------------------
    # 1) error_code 설정
    # ----------------------------
    # query는 자연어일 수 있으니 YOLO가 넘겨준 오류코드를 반드시 입력하도록 강제
    if not error_code:
        error_code = query  # fallback
    
    # ----------------------------
    # 2) RAG 상위 snippet join
    # ----------------------------
    ctx = "\n\n".join(snippets[:5]) if snippets else ""
    
    # ----------------------------
    # 3) 출처 정보 추출
    # ----------------------------
    citations = []
    if hits:
        for h in hits[:3]:
            src = h.get("source", {})
            citations.append({
                "section": src.get("section", ""),
                "pages": src.get("pages", ""),
                "excerpt": src.get("content", "")[:200]
            })
    
    # ----------------------------
    # 4) SYSTEM PROMPT (중요!)
    # ----------------------------
    SYSTEM_PROMPT = f"""당신은 AHU·기계설비 전문가입니다. 

입력된 error_code와 RAG 문서를 기반으로 

반드시 아래 Markdown 형식을 지켜서 정비 가이드를 출력하세요.

# 🔧 {error_code}

## 🟥 원인

- bullet 형태의 원인 나열 (최소 3개)

## 🛠 조치

1. 단계별 조치 (현장 실무자가 바로 수행할 수 있게)

2. 숫자 목록으로 정리

## ⚠ 주의사항

- 반드시 지켜야 하는 주의사항 bullet로 정리

규칙:

- 반드시 원인/조치/주의사항 3개 섹션을 모두 포함
- 각 섹션(원인/조치/주의사항)별로 하나의 답변만 반환
- Markdown 문법 유지
- RAG 문서 내용을 우선적으로 반영
- 불필요한 서론/요약/추가 내용 금지
- 각 섹션별(원인/조치/주의사항)로 한 개의 항목씩만 출력
"""
    
    # ----------------------------
    # 5) 최종 User Prompt
    # ----------------------------
    user_prompt = f"""아래는 RAG 검색으로 얻은 문서 내용입니다:

[RAG Snippets]

{ctx}

위 내용을 참고하여 반드시 정해진 Markdown 구조로 답변하세요.
"""

    if not gms_api_key:
        print(f"❌ [Generator] GMS_API_KEY가 설정되지 않았습니다.")
        raise ValueError("GMS_API_KEY가 설정되지 않았습니다. 환경 변수를 확인하세요.")
    
    try:
        print(f"🔵 [Generator] GPT-4o 호출 시작 (모델: {settings.GMS_MODEL_GENERATOR})")
        print(f"   Query: {query}")
        print(f"   Error Code: {error_code}")
        print(f"   Snippets 개수: {len(snippets)}")
        print(f"   Snippets 총 길이: {sum(len(s) for s in snippets)} bytes")
        text = call_openai_via_gms(
            model=settings.GMS_MODEL_GENERATOR,
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
            api_key=gms_api_key
        )
        print(f"✅ [Generator] GPT-4o 응답 수신 (길이: {len(text) if text else 0} bytes)")
        
        if not text or len(text.strip()) == 0:
            raise ValueError("GPT-4o가 빈 응답을 반환했습니다.")
        
        # 코드블록(```markdown`) 제거
        if "```" in text:
            parts = text.split("```")
            if len(parts) > 1:
                text = parts[1].replace("markdown", "").strip()
        
        # ----------------------------
        # 6) Markdown 파싱 (TTS용 텍스트 추출 + 섹션별 마크다운 추출)
        # ----------------------------
        import re
        lines = text.split("\n")
        
        # 원인 섹션 마크다운 추출
        causes_markdown_lines = []
        causes = []
        section = None
        for line in lines:
            if line.startswith("## 🟥 원인"):
                section = "cause"
                causes_markdown_lines.append(line)
                continue
            if line.startswith("## 🛠 조치"):
                section = None
                continue
            if section == "cause":
                causes_markdown_lines.append(line)
                if line.strip().startswith("-"):
                    causes.append(line.replace("-", "").strip())
        
        causes_markdown = "\n".join(causes_markdown_lines).strip()
        
        # 조치 섹션 마크다운 추출
        actions_markdown_lines = []
        actions = []
        section = None
        for line in lines:
            if line.startswith("## 🛠 조치"):
                section = "act"
                actions_markdown_lines.append(line)
                continue
            if line.startswith("## ⚠ 주의사항"):
                section = None
                continue
            if section == "act":
                actions_markdown_lines.append(line)
                m = re.match(r"^\d+[\.\)]\s*(.+)", line)
                if m:
                    actions.append(m.group(1).strip())
        
        actions_markdown = "\n".join(actions_markdown_lines).strip()
        
        # 주의사항 섹션 마크다운 추출
        warnings_markdown_lines = []
        warnings = []
        section = None
        for line in lines:
            if line.startswith("## ⚠ 주의사항"):
                section = "warn"
                warnings_markdown_lines.append(line)
                continue
            if line.startswith("#"):
                if section == "warn":
                    break
            if section == "warn":
                warnings_markdown_lines.append(line)
                if line.strip().startswith("-"):
                    warnings.append(line.replace("-", "").strip())
        
        warnings_markdown = "\n".join(warnings_markdown_lines).strip()
        
        # ----------------------------
        # 7) 구조화된 JSON 생성
        # ----------------------------
        result = {
            "error_code": error_code,
            "markdown_text": text,  # 전체 마크다운
            # TTS 변환용 (리스트 형태)
            "possible_causes": causes,
            "recommended_actions": [{"action": a, "priority": "medium"} for a in actions],
            "safety_warnings": warnings,
            # 모바일 렌더링용 (마크다운 형태)
            "possible_causes_markdown": causes_markdown,  # "## 🟥 원인\n- 필터 막힘...\n- 댐퍼..."
            "recommended_actions_markdown": actions_markdown,  # "## 🛠 조치\n1. 프리필터...\n2. 댐퍼..."
            "safety_warnings_markdown": warnings_markdown,  # "## ⚠ 주의사항\n- 압력 1.5bar..."
            "query": query,
            "citations": citations
        }
        
        print(f"✅ [Generator] 답변 생성 완료: error_code={error_code}, 원인={len(causes)}개, 조치={len(actions)}개, 주의사항={len(warnings)}개")
        
        # ----------------------------
        # 8) TTS friendly 변환
        # ----------------------------
        tts_parts = []
        if causes and actions and warnings:
            tts_parts.append(f"{error_code}에 대한 정비 가이드입니다.")
            tts_parts.append("원인은 " + ", ".join(causes[:3]) + " 등이 있습니다.")
            tts_parts.append("조치 단계는 " + ", ".join(actions[:3]) + " 입니다.")
            tts_parts.append("주의사항으로는 " + ", ".join(warnings[:2]) + "가 있습니다.")
        else:
            # Fallback: 기존 방식
            tts_text_parts = []
            tts_text_parts.append(f"{error_code}에 대한 정비 가이드입니다.")
            if causes:
                tts_text_parts.append("가능한 원인은 다음과 같습니다.")
                for i, cause in enumerate(causes[:5], 1):
                    tts_text_parts.append(f"{i}번째로, {cause}")
            if actions:
                tts_text_parts.append("다음과 같이 조치하세요.")
                step_number_map = {
                    1: "첫 번째", 2: "두 번째", 3: "세 번째", 4: "네 번째",
                    5: "다섯 번째", 6: "여섯 번째", 7: "일곱 번째", 8: "여덟 번째",
                    9: "아홉 번째", 10: "열 번째"
                }
                for i, action in enumerate(actions[:10], 1):
                    step_word = step_number_map.get(i, f"{i}번째")
                    tts_text_parts.append(f"{step_word}로, {action}")
            if warnings:
                tts_text_parts.append("중요한 주의사항입니다.")
                for warning in warnings:
                    tts_text_parts.append(warning)
            tts_parts = tts_text_parts
        
        result["tts_text"] = format_for_tts(". ".join(tts_parts))
        
        # ----------------------------
        # 9) 각 섹션별 TTS 변환
        # ----------------------------
        from app.services.tts_service import text_to_speech
        
        # possible_causes TTS
        causes_audio = None
        causes_audio_encoding = None
        if causes:
            causes_text = "가능한 원인은 다음과 같습니다. " + ". ".join(causes)
            try:
                causes_tts = text_to_speech(format_for_tts(causes_text))
                causes_audio = causes_tts.get("audio_content")
                causes_audio_encoding = causes_tts.get("mime_type")
            except Exception as e:
                print(f"⚠️ possible_causes TTS 변환 실패: {e}")
        
        # recommended_actions TTS
        actions_audio = None
        actions_audio_encoding = None
        if actions:
            actions_text = "조치 방법은 다음과 같습니다. "
            step_number_map = {
                1: "첫 번째", 2: "두 번째", 3: "세 번째", 4: "네 번째",
                5: "다섯 번째", 6: "여섯 번째", 7: "일곱 번째", 8: "여덟 번째",
                9: "아홉 번째", 10: "열 번째"
            }
            for i, action in enumerate(actions, 1):
                step_word = step_number_map.get(i, f"{i}번째")
                actions_text += f"{step_word}로, {action}. "
            try:
                actions_tts = text_to_speech(format_for_tts(actions_text))
                actions_audio = actions_tts.get("audio_content")
                actions_audio_encoding = actions_tts.get("mime_type")
            except Exception as e:
                print(f"⚠️ recommended_actions TTS 변환 실패: {e}")
        
        # safety_warnings TTS
        warnings_audio = None
        warnings_audio_encoding = None
        if warnings:
            warnings_text = "중요한 주의사항입니다. " + ". ".join(warnings)
            try:
                warnings_tts = text_to_speech(format_for_tts(warnings_text))
                warnings_audio = warnings_tts.get("audio_content")
                warnings_audio_encoding = warnings_tts.get("mime_type")
            except Exception as e:
                print(f"⚠️ safety_warnings TTS 변환 실패: {e}")
        
        # 각 섹션별 TTS 정보 추가
        result["possible_causes_audio"] = causes_audio
        result["possible_causes_audio_encoding"] = causes_audio_encoding
        result["recommended_actions_audio"] = actions_audio
        result["recommended_actions_audio_encoding"] = actions_audio_encoding
        result["safety_warnings_audio"] = warnings_audio
        result["safety_warnings_audio_encoding"] = warnings_audio_encoding
        
        return result
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ [Generator] GPT 호출 오류: {type(e).__name__}: {str(e)}")
        print(f"   상세 오류:\n{error_trace}")
        print(f"   Query: {query}")
        print(f"   Error Code: {error_code}")
        print(f"   Snippets 개수: {len(snippets) if snippets else 0}")
        
        # Fallback: RAG snippets 기반 간단한 답변 생성
        print(f"⚠️ [Generator] Fallback 모드: RAG snippets 기반 간단한 답변 생성 시도")
        try:
            fallback_result = _generate_fallback_answer(error_code, snippets, citations)
            if fallback_result:
                print(f"✅ [Generator] Fallback 답변 생성 성공")
                return fallback_result
        except Exception as fallback_error:
            print(f"❌ [Generator] Fallback 답변 생성도 실패: {fallback_error}")
        
        return {
            "error_code": error_code,
            "markdown_text": "",
            "possible_causes": [],
            "recommended_actions": [],
            "safety_warnings": [],
            "possible_causes_markdown": "",
            "recommended_actions_markdown": "",
            "safety_warnings_markdown": "",
            "possible_causes_audio": None,
            "possible_causes_audio_encoding": None,
            "recommended_actions_audio": None,
            "recommended_actions_audio_encoding": None,
            "safety_warnings_audio": None,
            "safety_warnings_audio_encoding": None,
            "tts_text": "",
            "query": query,
            "citations": citations
        }

