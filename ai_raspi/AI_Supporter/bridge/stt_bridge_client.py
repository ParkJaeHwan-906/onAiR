"""
STT 브리지 클라이언트 (Python 3.13용)
Python 3.10 브리지 서버에서 STT 결과를 받아서
Socket.IO로 FastAPI 서버에 전송하는 클라이언트
"""
import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SttBridgeClient:
    """
    STT 브리지 클라이언트
    Python 3.10 브리지 서버에서 STT 결과를 폴링하여 Socket.IO로 전송
    """
    def __init__(self, bridge_url: str = "http://127.0.0.1:8888", poll_interval: float = 0.1):
        """
        Args:
            bridge_url: 브리지 서버 URL
            poll_interval: 폴링 간격 (초)
        """
        self.bridge_url = bridge_url
        self.poll_interval = poll_interval
        self.is_running = False
        self.poll_task = None
        self.socketio_client = None  # Socket.IO 클라이언트 (외부에서 주입)
    
    def set_socketio_client(self, socketio_client):
        """Socket.IO 클라이언트 설정"""
        self.socketio_client = socketio_client
        logger.info("✅ Socket.IO 클라이언트가 브리지 클라이언트에 등록되었습니다.")
    
    async def poll_stt_results(self):
        """STT 결과를 폴링하여 Socket.IO로 전송"""
        async with aiohttp.ClientSession() as session:
            while self.is_running:
                try:
                    # 브리지 서버에서 STT 결과 폴링
                    async with session.get(f"{self.bridge_url}/stt/poll", timeout=aiohttp.ClientTimeout(total=1)) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get("has_result") and data.get("result"):
                                result = data["result"]
                                
                                # Socket.IO 클라이언트가 설정되어 있고 연결되어 있으면 전송
                                if self.socketio_client and self.socketio_client.is_connected():
                                    success = await self.socketio_client.emit_stt_result(result)
                                    if success:
                                        logger.info(f"✅ STT 결과 전송 완료: {result.get('type')} - {result.get('text', '')[:50]}...")
                                    else:
                                        logger.warning("⚠️ STT 결과 전송 실패")
                                else:
                                    logger.warning("⚠️ Socket.IO 클라이언트가 연결되지 않았습니다. STT 결과 대기 중...")
                    
                    # 폴링 간격 대기
                    await asyncio.sleep(self.poll_interval)
                    
                except asyncio.TimeoutError:
                    # 타임아웃은 정상 (결과가 없을 때)
                    await asyncio.sleep(self.poll_interval)
                except aiohttp.ClientError as e:
                    logger.warning(f"⚠️ 브리지 서버 연결 오류: {e} (재시도 중...)")
                    await asyncio.sleep(self.poll_interval * 2)  # 오류 시 더 긴 대기
                except Exception as e:
                    logger.error(f"❌ STT 결과 폴링 오류: {e}")
                    await asyncio.sleep(self.poll_interval)
    
    async def start(self):
        """브리지 클라이언트 시작"""
        if self.is_running:
            logger.warning("⚠️ 브리지 클라이언트가 이미 실행 중입니다.")
            return
        
        self.is_running = True
        self.poll_task = asyncio.create_task(self.poll_stt_results())
        logger.info(f"🚀 STT 브리지 클라이언트 시작: {self.bridge_url}")
        logger.info("   Python 3.10 브리지 서버에서 STT 결과를 폴링합니다.")
    
    async def stop(self):
        """브리지 클라이언트 중지"""
        self.is_running = False
        if self.poll_task:
            self.poll_task.cancel()
            try:
                await self.poll_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 STT 브리지 클라이언트 중지")
    
    async def check_bridge_server(self) -> bool:
        """브리지 서버 연결 확인"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.bridge_url}/health", timeout=aiohttp.ClientTimeout(total=2)) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ 브리지 서버 연결 확인: {data}")
                        return True
        except Exception as e:
            logger.warning(f"⚠️ 브리지 서버 연결 실패: {e}")
            return False
        return False

