from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import List
from app.core.model_loader import get_phi3_embedding

router = APIRouter(prefix="/api", tags=["Embedding"])

class EmbeddingRequest(BaseModel):
    text: str

class EmbeddingResponse(BaseModel):
    embedding: List[float]
    dimension: int

@router.post("/embedding")
def get_text_embedding(request: EmbeddingRequest = Body(...)) -> EmbeddingResponse:
    """
    텍스트를 Phi-3 임베딩 벡터로 변환하여 반환
    
    Args:
        request: 텍스트가 포함된 요청
        
    Returns:
        3072차원 FloatArray (List[float])
    """
    try:
        # 입력 검증
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="텍스트가 비어있습니다.")
        
        # 임베딩 추출
        embedding_array = get_phi3_embedding(request.text.strip())
        
        # numpy 배열을 Python 리스트로 변환
        embedding_list = embedding_array.tolist()
        
        return EmbeddingResponse(
            embedding=embedding_list,
            dimension=len(embedding_list)
        )
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Phi-3 모델이 사용 불가능합니다: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"임베딩 생성 중 오류 발생: {str(e)}"
        )

