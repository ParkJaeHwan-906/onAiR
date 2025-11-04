"""
HTTP POST webhook 클라이언트
앱 서버에 stt_start 알림을 전송합니다.
"""
import requests
import logging
from config import settings

logger = logging.getLogger(__name__)

def send_stt_start_webhook():
    """
    앱 서버에 stt_start 알림을 HTTP POST로 전송합니다.
    
    Returns:
        bool: 전송 성공 여부
    """
    try:
        url = f"{settings.APP_SERVER_URL}{settings.WEBHOOK_ENDPOINT}"
        payload = {"type": "stt_start", "message": "STT 세션이 시작되었습니다."}
        
        response = requests.post(
            url,
            json=payload,
            timeout=5.0,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Webhook 전송 성공: {url}")
            return True
        else:
            logger.warning(f"⚠️ Webhook 전송 실패: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Webhook 전송 오류: {e}")
        return False

