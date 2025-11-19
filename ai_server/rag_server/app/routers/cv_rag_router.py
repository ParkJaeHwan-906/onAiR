from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from app.services.retrieve_service import hybrid_retrieve, rerank
from app.services.generator import llm_generate_answer
from app.services.tts_service import text_to_speech
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["CV RAG"])

class CvDetectionRequest(BaseModel):
    """YOLO CV 탐지 결과 (이상 탐지 상황)"""
    detected: bool
    device_type: str
    modules: List[Dict[str, Any]]
    anomalies: Dict[str, Dict[str, Any]]
    message: Optional[str] = None

class CvRagResponse(BaseModel):
    """CV 탐지 결과 기반 RAG 답변"""
    query: str
    answer_text: str
    structured_answer: Dict[str, Any]
    audio_content: Optional[str] = None
    audio_encoding: Optional[str] = None
    citations: List[Dict[str, Any]]
    rag_debug_info: Optional[Dict[str, Any]] = None  # RAG 성능 점검용 디버그 정보

@router.post("/cv/rag")
def process_cv_detection_rag(
    request: CvDetectionRequest = Body(...),
    include_debug: bool = Query(True, description="RAG 디버그 정보 포함 여부 (기본값: True)")
) -> CvRagResponse:
    """
    YOLO CV 탐지 결과를 받아서 RAG 기반 GPT-4o 답변 생성
    
    실제 서비스 로직을 그대로 재사용합니다 (socket_handler.py의 handle_intent_audio_completed 로직)
    
    Args:
        request: CV 탐지 결과
    """
    try:
        # 1. CV 결과에서 쿼리 생성 (socket_handler.py 564-583줄 로직)
        anomalies = request.anomalies
        device_type = request.device_type
        
        query_parts = []
        
        # 장비 유형
        if device_type and device_type != "unknown":
            query_parts.append(f"{device_type}에서")
        
        # 모듈별 이상 탐지 (detail 필드 포함)
        detected_modules = []
        for module_name, module_res in anomalies.items():
            if isinstance(module_res, dict) and module_res.get("status") == "anomaly":
                # detail 필드가 있으면 module_name.detail 형식으로 사용
                detail = module_res.get("detail")
                if detail:
                    detected_modules.append(f"{module_name}.{detail}")
                else:
                    detected_modules.append(module_name)
        
        if detected_modules:
            query_parts.append(f"{', '.join(detected_modules)}에서 이상이 탐지되었습니다")
        else:
            query_parts.append("이상이 탐지되었습니다")
        
        query = " ".join(query_parts)
        
        # 2. RAG 검색 (Hybrid Retrieve + Rerank) - socket_handler.py 597-598줄 로직
        base_hits = hybrid_retrieve(query, top_k=settings.TOP_K)
        hits = rerank(query, base_hits, top_k=settings.RERANK_TOP_K)
        used_hits = hits[:5]
        
        # RAG 디버그 정보 수집
        rag_debug_info = None
        if include_debug:
            rag_debug_info = {
                "query": query,
                "retrieval_stats": {
                    "hybrid_retrieved_count": len(base_hits),
                    "reranked_count": len(hits),
                    "used_count": len(used_hits)
                },
                "retrieved_documents": [
                    {
                        "rank": idx + 1,
                        "section": hit.get("source", {}).get("section", ""),
                        "pages": hit.get("source", {}).get("pages", []),
                        "scores": {
                            "hybrid_score": hit.get("hybrid_score", 0.0),
                            "rerank_score": hit.get("rerank_score", 0.0),
                            "dense_norm": hit.get("dense_norm", 0.0),
                            "sparse_norm": hit.get("sparse_norm", 0.0)
                        },
                        "content_preview": hit.get("source", {}).get("content", "")[:200] + "..."
                    }
                    for idx, hit in enumerate(used_hits)
                ],
                "search_settings": {
                    "top_k": settings.TOP_K,
                    "rerank_top_k": settings.RERANK_TOP_K,
                    "hybrid_alpha": settings.HYBRID_ALPHA,
                    "rerank_weight": settings.RERANK_WEIGHT
                }
            }
        
        if not used_hits:
            answer_text = f"{query}에 대한 관련 문서를 찾을 수 없습니다."
            structured_answer = {
                "summary": answer_text,
                "tts_text": answer_text,
                "citations": []
            }
        else:
            # 3. GPT-4o로 최종 답변 생성 - socket_handler.py 625줄 로직
            snippets = [h["source"]["content"] for h in used_hits]
            
            # error_code 추출 (첫 번째 이상 탐지된 모듈의 detail 사용)
            error_code = None
            for module_name, module_res in anomalies.items():
                if isinstance(module_res, dict) and module_res.get("status") == "anomaly":
                    detail = module_res.get("detail")
                    if detail:
                        error_code = f"{module_name}.{detail}"
                    else:
                        error_code = module_name
                    break  # 첫 번째 이상만 사용
            
            print("=" * 60)
            print(f"🤖 [CV RAG Router] GPT-4o 호출 시작")
            print(f"   Query: {query}")
            print(f"   Error Code: {error_code}")
            print(f"   Snippets 개수: {len(snippets)}")
            print("=" * 60)
            
            try:
                answer_result = llm_generate_answer(query, snippets, error_code=error_code, hits=used_hits)
                answer_text = answer_result.get("tts_text") or answer_result.get("summary") or answer_result.get("answer", "")
                structured_answer = answer_result
                
                print("=" * 60)
                print(f"✅ [CV RAG Router] GPT-4o 답변 생성 완료")
                print(f"   Answer Text 길이: {len(answer_text) if answer_text else 0}")
                print(f"   Markdown Text 길이: {len(answer_result.get('markdown_text', ''))}")
                print(f"   Causes 개수: {len(answer_result.get('possible_causes', []))}")
                print(f"   Actions 개수: {len(answer_result.get('recommended_actions', []))}")
                print("=" * 60)
            except Exception as e:
                import traceback
                print("=" * 60)
                print(f"❌ [CV RAG Router] GPT-4o 호출 중 오류 발생")
                print(f"   오류 타입: {type(e).__name__}")
                print(f"   오류 메시지: {str(e)}")
                print(f"   상세 오류:\n{traceback.format_exc()}")
                print("=" * 60)
                # 예외를 다시 발생시켜서 HTTPException으로 변환
                raise
        
        # 4. TTS 변환 (무조건 수행)
        audio_content = None
        audio_encoding = None
        try:
            tts_result = text_to_speech(answer_text)
            audio_content = tts_result.get("audio_content")
            audio_encoding = tts_result.get("mime_type")
        except Exception as e:
            # TTS 실패해도 답변은 반환
            print(f"⚠️ TTS 변환 실패: {e}")
            pass
        
        # 5. 응답 구성
        return CvRagResponse(
            query=query,
            answer_text=answer_text,
            structured_answer=structured_answer,
            audio_content=audio_content,
            audio_encoding=audio_encoding,
            citations=structured_answer.get("citations", []),
            rag_debug_info=rag_debug_info
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"CV RAG 처리 중 오류 발생: {str(e)}"
        )

