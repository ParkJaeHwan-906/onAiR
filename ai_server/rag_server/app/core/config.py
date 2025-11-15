from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    JSONL_PATH: str = "app/data/samkos_cleaned.jsonl"
    FAISS_INDEX_PATH: str = "app/data/faiss_index/samkos.index"
    EMB_MODEL_NAME: str = "BAAI/bge-m3"
    EMB_ENCODING_MODE: str = "query"
    FAISS_METRIC: str = "cosine"

    USE_ELASTIC: bool = True  # Elasticsearch 활성화 (Hybrid Search 사용)
    ES_HOST: str = "http://localhost:9200"
    ES_INDEX: str = "samkos"

    USE_CROSS_ENCODER: bool = True
    CE_MODEL_NAME: str = "BAAI/bge-reranker-large"
    CE_MAXLEN: int = 256
    HYBRID_ALPHA: float = 0.82
    RERANK_TOP_K: int = 6
    RERANK_WEIGHT: float = 0.6
    TOP_K: int = 8

    ANSW_MIN_DOCS: int = 2
    ANSW_MIN_HYBRID: float = 0.12
    ANSW_MIN_RERANK: float = 5.2
    ANSW_MIN_QUERY_LEN: int = 6
    
    # Evidence Sufficiency Thresholds
    EVIDENCE_CONFIDENCE_THRESHOLD: float = 0.70  # rerank_score 기준 (기존 0.78에서 완화)
    EVIDENCE_COVERAGE_MIN: int = 2  # coverage_axes 최소값
    EVIDENCE_CONSISTENCY_THRESHOLD: float = 0.65  # consistency_score 기준 (기존 0.7에서 완화)
    EVIDENCE_SEMANTIC_THRESHOLD: float = 0.65  # retrieval_strength 기준 (기존 0.8에서 완화)
    
    # Coverage 완화: coverage_axes가 높으면 다른 조건 완화
    EVIDENCE_HIGH_COVERAGE_THRESHOLD: int = 4  # 이 값 이상이면 완화 적용
    EVIDENCE_HIGH_COVERAGE_CONSISTENCY_RELAX: float = 0.05  # consistency 완화 폭
    EVIDENCE_HIGH_COVERAGE_SEMANTIC_RELAX: float = 0.10  # semantic 완화 폭

    # ✅ 단일 GMS 키로 Gemini + GPT-4o 모두 사용
    LLM_PROVIDER: str = "gms"
    GMS_API_KEY: str | None = None
    GMS_MODEL_GATE: str = "gemini-2.0-flash"  # GMS에서 지원하는 모델명
    GMS_MODEL_GENERATOR: str = "gpt-4o"

    # =======================================
    # 💾 Conversation Memory (Redis)
    # =======================================
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    REDIS_PREFIX: str = "rag_chat"

    # =======================================
    # 🔤 Intent Classification
    # =======================================
    # Intent 분류는 Gemini-Flash를 사용합니다 (app/services/intent_service.py)
    # Phi-3 및 ONNX 모델 관련 설정 제거됨

    # # =======================================
    # # 🌐 FastAPI Server URL
    # # =======================================
    # # FastAPI 서버 URL (모바일 앱에서 접근할 URL)
    # # EC2 배포: "http://k13a407.p.ssafy.io/ai"
    # # 로컬 개발: "http://localhost:8000"
    # # 같은 네트워크: "http://192.168.0.100:8000"
    # FASTAPI_SERVER_URL: str = "http://k13a407.p.ssafy.io/ai"  # EC2 배포 URL
    # FASTAPI_SERVER_HOST: str = "0.0.0.0"  # 서버 바인딩 호스트 (EC2에서는 0.0.0.0 사용)
    # FASTAPI_SERVER_PORT: int = 8000  # 서버 포트
    
    # =======================================
    # 📞 WebRTC API URL
    # =======================================
    # WebRTC 요청 API URL
    # EC2 배포: "http://k13a407.p.ssafy.io" 또는 실제 API 서버 URL
    WEBRTC_API_URL: str = os.getenv("WEBRTC_API_URL", "https://onair.ai.kr/api")

    # =======================================
    # 🔊 TTS (Text-to-Speech) - GCP TTS
    # =======================================
    GCP_TTS_CREDENTIALS_PATH: str | None = None  # GCP 서비스 계정 JSON 키 파일 경로
    # 예: credentials/gcp-tts-key.json 또는 절대 경로
    GCP_TTS_VOICE_NAME: str = "ko-KR-Standard-A"  # 한국어 여성 음성
    GCP_TTS_LANGUAGE_CODE: str = "ko-KR"
    GCP_TTS_AUDIO_ENCODING: str = "MP3"  # MP3, LINEAR16, OGG_OPUS 등

    # =======================================
    # 🐛 디버그 모드 (단계별 수동 실행)
    # =======================================
    DEBUG_STEP_BY_STEP: bool = False  # True: 각 단계마다 파일 트리거 대기, False: 자동 진행
    DEBUG_STEP_TRIGGER_FILE: str = "/tmp/next_step"  # 다음 단계 진행 트리거 파일 경로
    DEBUG_STEP_WAIT_TIMEOUT: int = 300  # 최대 대기 시간 (초, 기본 5분)

    class Config:
        env_file = ".env"
        extra = "ignore"
        # 환경 변수 우선순위: 환경 변수 > .env 파일
        # Docker 컨테이너에서는 환경 변수로 전달되므로 env_file_encoding 명시
        env_file_encoding = 'utf-8'
        case_sensitive = False  # 대소문자 구분 안 함

settings = Settings()

# 디버그: API 키 로드 상태 확인 (서버 시작 시 한 번만 출력)

env_gms_key = os.getenv("GMS_API_KEY")
if env_gms_key:
    print(f"🔍 [Config] 환경 변수 GMS_API_KEY 발견: {env_gms_key[:10]}... (길이: {len(env_gms_key)})")
else:
    print("⚠️ [Config] 환경 변수 GMS_API_KEY가 설정되지 않았습니다.")

if settings.GMS_API_KEY:
    print(f"✅ [Config] Settings.GMS_API_KEY 로드 성공: {settings.GMS_API_KEY[:10]}... (길이: {len(settings.GMS_API_KEY)})")
else:
    print("❌ [Config] Settings.GMS_API_KEY가 None이거나 빈 문자열입니다.")
    print("   가능한 원인:")
    print("   1. .env 파일에 GMS_API_KEY가 없음")
    print("   2. Docker 환경 변수 GMS_API_KEY가 전달되지 않음")
    print("   3. Jenkins credentials에 GMS_API_KEY가 설정되지 않음")
