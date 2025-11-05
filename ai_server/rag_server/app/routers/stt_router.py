from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.core.model_loader import get_phi3_embedding

router = APIRouter(prefix="/api/stt", tags=["STT"])

class STTResultRequest(BaseModel):
    type: str  # "final" | "interim" | "error" | "info"
    text: str
    confidence: Optional[float] = None
    session_id: Optional[str] = None  # Streaming STT용 세션 ID

class STTResultResponse(BaseModel):
    success: bool
    embedding: Optional[List[float]] = None
    dimension: Optional[int] = None
    message: str

@router.post("/buffered")
async def handle_buffered_stt(request: STTResultRequest = Body(...)) -> STTResultResponse:
    """
    버퍼링 STT 결과를 수신하여 Phi-3 임베딩을 추출하고 모바일로 전송
    
    플로우:
    1. 라즈베리파이 → Socket.IO (stt_result 이벤트)
    2. Socket.IO → FastAPI POST /api/stt/buffered
    3. FastAPI → Phi-3 임베딩 추출
    4. FastAPI → Socket.IO로 모바일에게 전송
    
    Args:
        request: STT 결과
            {
                "type": "final" | "interim" | "error" | "info",
                "text": "인식된 텍스트",
                "confidence": 0.95 (optional)
            }
    
    Returns:
        {
            "success": true,
            "embedding": [0.123, 0.456, ...],  # 3072차원 (type="final"일 때만)
            "dimension": 3072,
            "message": "처리 완료"
        }
    """
    try:
        stt_type = request.type
        stt_text = request.text.strip()
        
        # 입력 검증
        if not stt_text:
            return STTResultResponse(
                success=False,
                message="STT 텍스트가 비어있습니다."
            )
        
        # session_id가 있으면 Streaming STT → Clarify 처리로 전달
        if request.session_id:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8000/api/clarify/streaming",
                        json={
                            "session_id": request.session_id,
                            "type": stt_type,
                            "text": stt_text,
                            "confidence": request.confidence
                        },
                        timeout=30.0
                    )
                    if response.status_code == 200:
                        return STTResultResponse(
                            success=True,
                            message=f"Streaming STT 처리 완료: '{stt_text[:50]}...'"
                        )
            except Exception as e:
                print(f"⚠️ Clarify 처리 중 오류: {e}")
                return STTResultResponse(
                    success=False,
                    message=f"Clarify 처리 실패: {str(e)}"
                )
        
        # 버퍼링 STT: final 타입만 임베딩 추출 (interim은 스킵)
        if stt_type == "final":
            try:
                # Phi-3 임베딩 추출
                embedding_array = get_phi3_embedding(stt_text)
                embedding_list = embedding_array.tolist()
                
                # Socket.IO를 통해 모바일로 전송
                # socket_manager는 ai_ar 프로젝트에 있음
                try:
                    import sys
                    import os
                    current_file_dir = os.path.dirname(os.path.abspath(__file__))
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir))))
                    ai_ar_path = os.path.join(project_root, "ai_ar")
                    
                    if os.path.exists(ai_ar_path) and ai_ar_path not in sys.path:
                        sys.path.insert(0, ai_ar_path)
                    
                    from app.sockets.socket_manager import broadcast_to
                    
                    # 모바일로 임베딩 전송
                    await broadcast_to("mobile", "embedding_result", {
                        "text": stt_text,
                        "embedding": embedding_list,
                        "dimension": len(embedding_list),
                        "confidence": request.confidence
                    })
                    
                    print(f"✅ STT 텍스트 처리 완료: '{stt_text[:50]}...' → 모바일로 임베딩 전송")
                    
                except ImportError as e:
                    print(f"⚠️ socket_manager를 찾을 수 없습니다: {e}. 임베딩만 반환합니다.")
                except Exception as e:
                    print(f"⚠️ Socket.IO 전송 중 오류 발생: {e}. 임베딩은 반환합니다.")
                
                return STTResultResponse(
                    success=True,
                    embedding=embedding_list,
                    dimension=len(embedding_list),
                    message=f"STT 텍스트 처리 완료: '{stt_text[:50]}...'"
                )
                
            except RuntimeError as e:
                return STTResultResponse(
                    success=False,
                    message=f"Phi-3 모델이 사용 불가능합니다: {str(e)}"
                )
            except Exception as e:
                return STTResultResponse(
                    success=False,
                    message=f"임베딩 생성 중 오류 발생: {str(e)}"
                )
        
        elif stt_type == "interim":
            # 중간 결과는 임베딩 추출하지 않고 모바일로만 전달 (socket_manager에서 처리)
            return STTResultResponse(
                success=True,
                message=f"중간 결과 수신: '{stt_text[:50]}...' (임베딩 추출 안 함)"
            )
        
        else:
            # error, info 등의 타입은 그냥 수신 확인만
            return STTResultResponse(
                success=True,
                message=f"STT 메타데이터 수신: type={stt_type}"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"STT 결과 처리 중 오류 발생: {str(e)}"
        )

