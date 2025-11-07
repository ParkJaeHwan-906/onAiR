from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    JSONL_PATH: str = "app/data/samkos_cleaned.jsonl"
    FAISS_INDEX_PATH: str = "app/data/faiss_index/samkos.index"
    EMB_MODEL_NAME: str = "BAAI/bge-m3"
    EMB_ENCODING_MODE: str = "query"
    FAISS_METRIC: str = "cosine"

    USE_ELASTIC: bool = True  # Hybrid 검색을 위해 기본값을 True로 변경
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
    GMS_MODEL_GATE: str = "gemini-1.5-flash"
    GMS_MODEL_GENERATOR: str = "gpt-4o"

    # =======================================
    # 💾 Conversation Memory (Redis)
    # =======================================
    REDIS_URL: str = "redis://localhost:6380/0"
    REDIS_PREFIX: str = "rag_chat"

    # =======================================
    # 🔤 Intent Classification
    # =======================================
    # Intent 분류는 Gemini-Flash를 사용합니다 (app/services/intent_service.py)
    # Phi-3 및 ONNX 모델 관련 설정 제거됨

    # =======================================
    # 🔊 TTS (Text-to-Speech) - GCP TTS
    # =======================================
    GCP_TTS_CREDENTIALS_PATH: str | None = None  # GCP 서비스 계정 JSON 키 파일 경로
    # 예: credentials/gcp-tts-key.json 또는 절대 경로
    GCP_TTS_VOICE_NAME: str = "ko-KR-Standard-A"  # 한국어 여성 음성
    GCP_TTS_LANGUAGE_CODE: str = "ko-KR"
    GCP_TTS_AUDIO_ENCODING: str = "MP3"  # MP3, LINEAR16, OGG_OPUS 등

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
