from fastapi import APIRouter, Body, HTTPException
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

@router.post("/cv/rag")
def process_cv_detection_rag(request: CvDetectionRequest = Body(...)) -> CvRagResponse:
    """
    YOLO CV 탐지 결과를 받아서 RAG 기반 GPT-4o 답변 생성
    
    실제 서비스 로직을 그대로 재사용합니다 (socket_handler.py의 handle_intent_audio_completed 로직)
    """
    try:
        # 1. CV 결과에서 쿼리 생성 (socket_handler.py 564-583줄 로직)
        anomalies = request.anomalies
        device_type = request.device_type
        
        query_parts = []
        
        # 장비 유형
        if device_type and device_type != "unknown":
            query_parts.append(f"{device_type}에서")
        
        # 모듈별 이상 탐지
        detected_modules = []
        for module_name, module_res in anomalies.items():
            if isinstance(module_res, dict) and module_res.get("status") == "anomaly":
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
            answer_result = llm_generate_answer(query, snippets, used_hits)
            answer_text = answer_result.get("tts_text") or answer_result.get("summary") or answer_result.get("answer", "")
            structured_answer = answer_result
        
        # 4. TTS 변환 (선택적) - socket_handler.py 646줄 로직
        audio_content = None
        audio_encoding = None
        try:
            tts_result = text_to_speech(answer_text)
            audio_content = tts_result.get("audio_content")
            audio_encoding = tts_result.get("mime_type")
        except Exception as e:
            # TTS 실패해도 답변은 반환
            pass
        
        # 5. 응답 구성
        return CvRagResponse(
            query=query,
            answer_text=answer_text,
            structured_answer=structured_answer,
            audio_content=audio_content,
            audio_encoding=audio_encoding,
            citations=structured_answer.get("citations", [])
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"CV RAG 처리 중 오류 발생: {str(e)}"
        )

