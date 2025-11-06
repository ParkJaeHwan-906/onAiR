"""
FastAPI 서버로 STT 결과를 전송하는 클라이언트
스트리밍 모드에서 사용됩니다.
"""
import aiohttp
import asyncio
import logging
import uuid
from config import settings

logger = logging.getLogger(__name__)

class FastApiClient:
    def __init__(self):
        self.server_url = settings.FASTAPI_SERVER_URL
        self.rag_endpoint = settings.RAG_CHAT_ENDPOINT
        self.session_id = None  # 세션 ID는 첫 요청 시 생성

    async def send_text(self, text: str, session_id: str = None):
        """
        STT 텍스트를 FastAPI 서버로 전송합니다.
        
        Args:
            text: STT로 인식된 텍스트
            session_id: 세션 ID (없으면 새로 생성)
        
        Returns:
            dict: FastAPI 서버 응답
        """
        if not session_id:
            # 세션 ID가 없으면 UUID 생성
            session_id = str(uuid.uuid4())
            self.session_id = session_id
        
        url = f"{self.server_url}{self.rag_endpoint}"
        payload = {
            "query": text,
            "session_id": session_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ FastAPI 서버 응답 수신: {url}")
                        # 세션 ID 저장 (다음 요청에서 사용)
                        if "session_id" in result:
                            self.session_id = result["session_id"]
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ FastAPI 서버 오류: {response.status} - {error_text}")
                        return {"error": error_text, "status": response.status}
        except asyncio.TimeoutError:
            logger.error(f"❌ FastAPI 서버 타임아웃: {url}")
            return {"error": "timeout"}
        except Exception as e:
            logger.error(f"❌ FastAPI 서버 연결 오류: {e}")
            return {"error": str(e)}

    def get_session_id(self):
        """현재 세션 ID를 반환합니다."""
        return self.session_id

    def reset_session(self):
        """세션을 초기화합니다."""
        self.session_id = None
