import os

# === GCP STT 설정 ===
# GCP 서비스 계정 키 파일 경로 (라즈베리 내 실제 경로로 변경)
GCP_CREDENTIAL_PATH = "/home/pi/AI_Supporter/secrets/stt-key.json"
LANGUAGE = "ko-KR"

# === 오디오 설정 ===
MIC_RATE = 48000        # 마이크 실제 샘플레이트 (Hz) - 마이크 하드웨어 스펙
RATE = 16000            # STT용 샘플레이트 (Hz) - GCP STT는 16000Hz 사용
CHUNK_MS = 100          # 청크 단위 (ms)
CHANNELS = 1            # 마이크 채널 (모노)
DEVICE_INDEX = None     # 기본 마이크 자동 선택

# === STT 버퍼링 설정 ===
STT_BUFFER_DURATION_SEC = 4.0  # 3~5초 사이 추천

# === STT 스트리밍 설정 ===
SILENCE_TIMEOUT_SEC = 0.5  # 침묵 타임아웃 (초)

# === FastAPI 서버 설정 ===
# FastAPI 서버 URL (Socket.IO 서버도 통합되어 있음)
# EC2 배포 주소: "http://k13a407.p.ssafy.io/ai"
# 로컬 테스트 시: "http://localhost:8000"
FASTAPI_SERVER_URL = "http://k13a407.p.ssafy.io/ai"

# === 디버그 모드 (단계별 수동 실행) ===
DEBUG_STEP_BY_STEP = True  # True: 각 단계마다 파일 트리거 대기, False: 자동 진행
DEBUG_STEP_TRIGGER_FILE = "/tmp/next_step_raspi"  # 다음 단계 진행 트리거 파일 경로
DEBUG_STEP_WAIT_TIMEOUT = 300  # 최대 대기 시간 (초, 기본 5분)

