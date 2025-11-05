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
SILENCE_TIMEOUT_SEC = float(os.getenv("SILENCE_TIMEOUT_SEC", "3.0"))  # 침묵 타임아웃 (초)

# === FastAPI 서버 설정 ===
FASTAPI_SERVER_URL = os.getenv("FASTAPI_SERVER_URL", "http://localhost:8001")
RAG_CHAT_ENDPOINT = os.getenv("RAG_CHAT_ENDPOINT", "/rag/chat")
WS_CHAT_ENDPOINT = os.getenv("WS_CHAT_ENDPOINT", "/ws/chat")  # WebSocket 엔드포인트