from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.tts_service import text_to_speech

router = APIRouter(prefix="/api", tags=["TTS"])

class TTSRequest(BaseModel):
    text: str
    voice_name: Optional[str] = None
    language_code: Optional[str] = None
    audio_encoding: Optional[str] = None

class TTSResponse(BaseModel):
    audio_content: str  # Base64 인코딩된 오디오 데이터
    audio_encoding: str
    mime_type: str
    text_length: int

@router.post("/tts")
def generate_speech(request: TTSRequest = Body(...)) -> TTSResponse:
    """
    텍스트를 음성 파일로 변환 (GCP TTS)
    
    Args:
        request: 텍스트 및 음성 설정이 포함된 요청
        
    Returns:
        Base64 인코딩된 오디오 데이터 및 메타데이터
    """
    try:
        # 입력 검증
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="텍스트가 비어있습니다.")
        
        # 텍스트 길이 제한 (GCP TTS 제한: 5000자)
        max_length = 5000
        if len(request.text) > max_length:
            raise HTTPException(
                status_code=400, 
                detail=f"텍스트가 너무 깁니다. 최대 {max_length}자까지 지원됩니다."
            )
        
        # TTS 생성
        result = text_to_speech(
            text=request.text,
            voice_name=request.voice_name,
            language_code=request.language_code,
            audio_encoding=request.audio_encoding
        )
        
        return TTSResponse(
            audio_content=result["audio_content"],
            audio_encoding=result["audio_encoding"],
            mime_type=result["mime_type"],
            text_length=result["text_length"]
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"TTS 서비스 오류: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"음성 생성 중 오류 발생: {str(e)}"
        )

