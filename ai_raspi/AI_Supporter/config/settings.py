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
STT_BUFFER_DURATION_SEC = 2.0  # 버퍼링 STT 수행 시간 (초)

# === STT 스트리밍 설정 ===
SILENCE_TIMEOUT_SEC = 1.5  # 침묵 타임아웃 (초) - 한 문장이 끝났음을 감지하기 위한 대기 시간

# === FastAPI 서버 설정 ===
# FastAPI 서버 URL (Socket.IO 서버도 통합되어 있음)
# EC2 배포 주소: "https://onair.ai.kr"
# 로컬 테스트 시: "http://localhost:8000"
FASTAPI_SERVER_URL = "https://onair.ai.kr"

# === 디버그 모드 (단계별 수동 실행) ===
DEBUG_STEP_BY_STEP = True  # True: 각 단계마다 Enter 키 입력 대기, False: 자동 진행
DEBUG_STEP_TRIGGER_FILE = "/tmp/next_step_raspi"  # (사용 안 함) 레거시 설정, 키보드 입력 방식 사용
DEBUG_STEP_WAIT_TIMEOUT = 300  # (사용 안 함) 레거시 설정, 키보드 입력 방식 사용

# === Wakeword 재활성화 제어 ===
# 서비스 완료 후 wakeword 감지기를 자동 재활성화할지 여부
# - True: service_completed 수신 후 자동 재활성화
# - False: 개발자가 별도 시점에 수동으로 재활성화 (요청 사항)
REENABLE_WAKEWORD_AFTER_SERVICE = True

