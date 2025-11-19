"""
라즈베리파이 ConnectionManager 모듈

모든 통신은 Socket.IO를 통해 이루어지며, HTTP 서버는 사용하지 않습니다.
ConnectionManager는 Socket.IO 클라이언트와 STT 인스턴스를 관리합니다.
"""
from .websocket_manager import ConnectionManager

# ConnectionManager 인스턴스 생성 (Socket.IO 통신 관리용)
# 모든 통신은 Socket.IO를 통해 FastAPI 서버로 전송됩니다.
manager = ConnectionManager()

