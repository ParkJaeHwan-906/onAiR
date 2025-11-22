# app/services/final_guide.py
"""
정비 가이드 생성 서비스
CV 탐지 결과를 기반으로 RAG 검색 및 GPT-4o 답변 생성
"""
from typing import Dict, Any, List
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.generator import llm_generate_answer
from app.core.config import settings


async def generate_final_guide(
    device_type: str,
    modules: List[Dict[str, Any]],
    anomalies: Dict[str, Dict[str, Any]],
    cv_result: Dict[str, Any],
    broadcast_to_func  # broadcast_to 함수를 인자로 받음 (async 함수)
) -> Dict[str, Any]:
    """
    CV 탐지 이상 결과를 기반으로 전체 정비 가이드를 생성하고 모바일로 전송
    
    Args:
        device_type: 장비 타입 (예: "AHU")
        modules: 탐지된 모듈 목록
        anomalies: 이상 탐지 결과
        cv_result: CV 탐지 결과 전체
        broadcast_to_func: broadcast_to 함수 (의존성 주입)
    
    Returns:
        dict: 생성된 정비 가이드
    """
    print("=" * 60)
    print(f"📚 [단계 12] 전체 정비 가이드 생성 시작")
    print("=" * 60)
    
    # RAG용 질의 문장 생성
    query = _build_rag_query(device_type, anomalies)
    print(f"   Query: {query}")
    
    # RAG 검색
    try:
        base_hits = hybrid_retrieve(query, top_k=settings.TOP_K)
        hits = rerank(query, base_hits, top_k=settings.RERANK_TOP_K)
        used_hits = hits[:5]
        
        if not used_hits:
            print("⚠️ RAG 검색 결과가 없습니다.")
            structured_answer = _create_empty_answer(query)
        else:
            print(f"✅ RAG 검색 완료: {len(used_hits)}개 문서 발견")
            
            # GPT-4o로 최종 답변 생성
            print("=" * 60)
            print(f"🤖 [단계 13] GPT-4o로 전체 정비 가이드 생성 시작")
            print("=" * 60)
            
            snippets = [h["source"]["content"] for h in used_hits]
            error_code = _extract_error_code(anomalies)
            
            structured_answer = llm_generate_answer(
                query, snippets, error_code=error_code, hits=used_hits
            )
            print(f"✅ 전체 정비 가이드 생성 완료")
    except Exception as e:
        print(f"❌ RAG 검색 또는 답변 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        structured_answer = _create_empty_answer(query)
    
    answer_text = structured_answer.get("tts_text") or structured_answer.get("summary") or structured_answer.get("answer", "")
    
    # 모바일로 전체 정비 가이드 전송
    print("=" * 60)
    print(f"📤 [단계 14] 모바일로 전체 정비 가이드 전송 시작")
    print("=" * 60)
    await broadcast_to_func("mobile", "final_answer", {
        "answer": answer_text,
        "structured_answer": structured_answer,
        "audio_content": None,
        "audio_encoding": None,
        "citations": structured_answer.get("citations", []),
        "cv_detection_result": {
            "device_type": device_type,
            "modules": modules,
            "anomalies": anomalies,
            "message": cv_result.get('message', '')
        }
    })
    print("✅ 모바일로 전체 정비 가이드 전송 완료")
    print("=" * 60)
    
    # 라즈베리파이로 CV 탐지 성공 알림
    await broadcast_to_func("raspi", "cv_detection_success", cv_result.get('message', ''))
    
    return structured_answer


def _build_rag_query(device_type: str, anomalies: Dict[str, Any]) -> str:
    """RAG용 질의 문장 생성"""
    query_parts = []
    if device_type and device_type != "unknown":
        query_parts.append(f"{device_type}에서")
    
    # 모듈별 이상 탐지 (detail 필드 포함)
    detected_modules = []
    for module_name, module_res in anomalies.items():
        if isinstance(module_res, dict) and module_res.get("status") == "anomaly":
            detail = module_res.get("detail")
            if detail:
                detected_modules.append(f"{module_name}.{detail}")
            else:
                detected_modules.append(module_name)
    
    if detected_modules:
        query_parts.append(f"{', '.join(detected_modules)}에서 이상이 탐지되었습니다")
    else:
        query_parts.append("이상이 탐지되었습니다")
    
    return " ".join(query_parts)


def _extract_error_code(anomalies: Dict[str, Any]) -> str:
    """에러 코드 추출"""
    for module_name, module_res in anomalies.items():
        if isinstance(module_res, dict) and module_res.get("status") == "anomaly":
            detail = module_res.get("detail")
            if detail:
                return f"{module_name}.{detail}"
            else:
                return module_name
    return None


def _create_empty_answer(query: str) -> Dict[str, Any]:
    """빈 답변 생성"""
    answer_text = f"{query}에 대한 관련 문서를 찾을 수 없습니다."
    return {
        "error_code": query,
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
        "tts_text": answer_text,
        "query": query,
        "citations": []
    }

