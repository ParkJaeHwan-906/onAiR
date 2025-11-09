import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# === GCP STT 설정 ===
GCP_CREDENTIAL_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./secrets/stt-key.json")
LANGUAGE = os.getenv("LANGUAGE", "ko-KR")

# === 오디오 설정 ===
RATE = 16000
CHUNK_MS = 100
CHANNELS = 1
DEVICE_INDEX = os.getenv("DEVICE_INDEX", None)

# === STT 버퍼링 설정 ===
STT_BUFFER_DURATION_SEC = float(os.getenv("STT_BUFFER_DURATION_SEC", "4.0"))  # 3~5초

# === STT 스트리밍 설정 ===
SILENCE_TIMEOUT_SEC = float(os.getenv("SILENCE_TIMEOUT_SEC", "0.5"))  # 침묵 타임아웃 (초) - 명시적 타이머 기반 종료 감지

# === FastAPI 서버 설정 ===
# FastAPI 서버 URL (Socket.IO 서버도 여기에 통합되어 있음, 경로: /ai/ws)
# EC2 배포: "https://k13a407.p.ssafy.io/ai"
# 로컬 개발: "http://localhost:8000"
FASTAPI_SERVER_URL = os.getenv("FASTAPI_SERVER_URL", "https://k13a407.p.ssafy.io/ai")
RAG_CHAT_ENDPOINT = os.getenv("RAG_CHAT_ENDPOINT", "/rag/chat")
WS_CHAT_ENDPOINT = os.getenv("WS_CHAT_ENDPOINT", "/ws/chat")  # WebSocket 엔드포인트 (레거시)