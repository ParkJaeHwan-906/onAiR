from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging
from app.services.intent_service import classify_intent
from app.utils.retry import retry_with_backoff

router = APIRouter(prefix="/api/stt", tags=["STT"])
logger = logging.getLogger(__name__)

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
    버퍼링 STT 결과를 수신하여 Gemini-Flash로 Intent 분류하고 모바일로 전송
    
    플로우:
    1. 라즈베리파이 → Socket.IO (stt_result 이벤트)
    2. Socket.IO → FastAPI POST /api/stt/buffered
    3. FastAPI → Gemini-Flash로 Intent 분류
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
            "intent": "OPERATOR" | "AI_SUPPORTER",
            "confidence": 0.0~1.0,
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
                    # 재시도 로직 포함
                    async def call_clarify_api():
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
                        response.raise_for_status()
                        return response
                    
                    response = await retry_with_backoff(
                        call_clarify_api,
                        max_attempts=3,
                        initial_delay=1.0,
                        max_delay=5.0,
                        exceptions=(httpx.TimeoutException, httpx.HTTPStatusError, Exception)
                    )
                    
                    if response.status_code == 200:
                        return STTResultResponse(
                            success=True,
                            message=f"Streaming STT 처리 완료: '{stt_text[:50]}...'"
                        )
            except Exception as e:
                logger.error(f"⚠️ Clarify 처리 중 오류: {e}")
                return STTResultResponse(
                    success=False,
                    message=f"Clarify 처리 실패: {str(e)}"
                )
        
        # 버퍼링 STT: final 타입만 Intent 분류 (interim은 스킵)
        if stt_type == "final":
            try:
                # 1. 먼저 모바일로 SSE 연결 시작 요청 전송
                try:
                    import sys
                    import os
                    current_file_dir = os.path.dirname(os.path.abspath(__file__))
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir))))
                    ai_ar_path = os.path.join(project_root, "ai_ar")
                    ai_ar_app_path = os.path.join(ai_ar_path, "app")
                    
                    if os.path.exists(ai_ar_app_path) and ai_ar_app_path not in sys.path:
                        sys.path.insert(0, ai_ar_app_path)
                    
                    from sockets.socket_manager import broadcast_to
                    
                    await broadcast_to("mobile", "start_sse_connection", {
                        "text": stt_text,
                        "timestamp": None
                    })
                    logger.info(f"📡 모바일로 SSE 연결 시작 요청 전송: '{stt_text[:50]}...'")
                except Exception as e:
                    logger.warning(f"⚠️ SSE 연결 시작 요청 전송 실패: {e}")
                
                # 2. Gemini-Flash로 Intent 분류
                intent_result = classify_intent(stt_text)
                intent = intent_result.get("intent", "AI_SUPPORTER")
                intent_confidence = intent_result.get("confidence", 0.5)
                reasoning = intent_result.get("reasoning", "")
                
                # Socket.IO를 통해 모바일로 전송
                # socket_manager는 ai_ar 프로젝트에 있음
                try:
                    import sys
                    import os
                    current_file_dir = os.path.dirname(os.path.abspath(__file__))
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir))))
                    ai_ar_path = os.path.join(project_root, "ai_ar")
                    ai_ar_app_path = os.path.join(ai_ar_path, "app")
                    
                    if os.path.exists(ai_ar_app_path) and ai_ar_app_path not in sys.path:
                        sys.path.insert(0, ai_ar_app_path)
                    
                    from sockets.socket_manager import broadcast_to
                    
                    # 모바일로 Intent 결과 전송 (에러 핸들링 및 재시도)
                    try:
                        await broadcast_to("mobile", "intent_result", {
                            "text": stt_text,
                            "intent": intent,
                            "confidence": intent_confidence,
                            "reasoning": reasoning,
                            "stt_confidence": request.confidence
                        })
                        logger.info(f"✅ STT 텍스트 처리 완료: '{stt_text[:50]}...' → Intent: {intent} (신뢰도: {intent_confidence:.2f})")
                    except Exception as e:
                        logger.error(f"❌ Intent 결과 전송 실패: {e}, 재시도 중...")
                        # 재시도
                        try:
                            await retry_with_backoff(
                                broadcast_to,
                                max_attempts=2,
                                initial_delay=0.5,
                                exceptions=(Exception,),
                                device_types="mobile",
                                event="intent_result",
                                payload={
                                    "text": stt_text,
                                    "intent": intent,
                                    "confidence": intent_confidence,
                                    "reasoning": reasoning,
                                    "stt_confidence": request.confidence
                                }
                            )
                            logger.info(f"✅ Intent 결과 전송 재시도 성공")
                        except Exception as retry_error:
                            logger.error(f"❌ Intent 결과 전송 재시도 실패: {retry_error}")
                    
                except ImportError as e:
                    logger.warning(f"⚠️ socket_manager를 찾을 수 없습니다: {e}. Intent 결과만 반환합니다.")
                except Exception as e:
                    logger.warning(f"⚠️ Socket.IO 전송 중 오류 발생: {e}. Intent 결과는 반환합니다.")
                
                return STTResultResponse(
                    success=True,
                    message=f"STT 텍스트 처리 완료: '{stt_text[:50]}...' → Intent: {intent}"
                )
                
            except Exception as e:
                logger.error(f"❌ Intent 분류 중 오류 발생: {str(e)}")
                # 에러 발생 시 기본값으로 AI_SUPPORTER 반환
                return STTResultResponse(
                    success=False,
                    message=f"Intent 분류 중 오류 발생: {str(e)}"
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

