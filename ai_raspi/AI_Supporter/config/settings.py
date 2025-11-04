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
SILENCE_TIMEOUT_SEC = 2.0

# === 앱 서버 설정 ===
APP_SERVER_URL = os.getenv("APP_SERVER_URL", "http://localhost:8080")
WEBHOOK_ENDPOINT = os.getenv("WEBHOOK_ENDPOINT", "/api/stt/start")

# === STT 버퍼링 설정 ===
STT_BUFFER_DURATION_SEC = float(os.getenv("STT_BUFFER_DURATION_SEC", "4.0"))  # 3~5초