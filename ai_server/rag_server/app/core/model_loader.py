import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from app.core.config import settings

# Optional: Elastic
try:
    from elasticsearch import Elasticsearch
except Exception:
    Elasticsearch = None

# Optional: Phi-3 (for intent classification)
try:
    import torch
    from transformers import AutoModel, AutoTokenizer
    PHI3_AVAILABLE = True
except Exception:
    PHI3_AVAILABLE = False
    torch = None
    AutoModel = None
    AutoTokenizer = None

def load_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

print("Loading data, embedding model, FAISS index...")
DATA = load_jsonl(settings.JSONL_PATH)

# 각 row에 내부 id 부여(FAISS 인덱스와 동일 인덱스 사용)
for i, row in enumerate(DATA):
    row["_id"] = i

# Known subjects (equipment/parts/sections) from embedded dataset
def _build_known_subjects(rows):
    import re
    subjects = set()
    
    # 1) 구조화된 필드에서 추출
    candidate_keys = [
        "section",
        "equipment",
        "equipment_name",
        "title",
        "part",
        "subsection",
    ]
    for item in rows:
        for key in candidate_keys:
            val = item.get(key)
            if isinstance(val, str):
                norm = val.strip().replace(" ", "").lower()
                if norm:
                    subjects.add(norm)
    
    # 2) content 텍스트에서 장비명/부품명 추출 (한글 키워드 패턴)
    equipment_keywords = [
        "송풍기", "댐퍼", "필터", "모터", "펌프", "밸브", "냉각기", "가열기",
        "베어링", "벨트", "드레인", "엘리미네이터", "팬", "콤프레셔",
        "전동기", "히터", "코일", "압축기", "배수펌프", "냉수펌프", "온수펌프"
    ]
    
    for item in rows:
        content = item.get("content", "")
        if isinstance(content, str):
            content_lower = content.lower()
            # 장비명이 content에 언급되어 있으면 추출
            for kw in equipment_keywords:
                if kw in content_lower:
                    subjects.add(kw.lower().replace(" ", ""))
    
    return subjects

KNOWN_SUBJECTS = _build_known_subjects(DATA)
print(f"✓ Known subjects loaded: {len(KNOWN_SUBJECTS)}")

# BGE-M3 모델 로드
print(f"📦 Loading embedding model: {settings.EMB_MODEL_NAME}")
MODEL = SentenceTransformer(settings.EMB_MODEL_NAME)

# FAISS 인덱스 로드 및 차원 검증
print(f"📦 Loading FAISS index: {settings.FAISS_INDEX_PATH}")
INDEX = faiss.read_index(settings.FAISS_INDEX_PATH)

# 모델 임베딩 차원 확인
model_dim = MODEL.get_sentence_embedding_dimension()
index_dim = INDEX.d

print(f"✓ Model embedding dimension: {model_dim}")
print(f"✓ FAISS index dimension: {index_dim}")

if model_dim != index_dim:
    raise ValueError(
        f"❌ 차원 불일치! 모델 차원({model_dim})과 FAISS 인덱스 차원({index_dim})이 일치하지 않습니다.\n"
        f"   BGE-M3 모델을 사용하려면 1024차원으로 FAISS 인덱스를 재구축해야 합니다."
    )

# CrossEncoder (옵션)
CE = None
if settings.USE_CROSS_ENCODER:
    print(f"📦 Loading CrossEncoder: {settings.CE_MODEL_NAME}")
    CE = CrossEncoder(settings.CE_MODEL_NAME, max_length=settings.CE_MAXLEN)

# Elastic (옵션)
ES = None
if settings.USE_ELASTIC and Elasticsearch is not None:
    try:
        print(f"🔌 Connecting Elasticsearch: {settings.ES_HOST} / index={settings.ES_INDEX}")
        ES = Elasticsearch(settings.ES_HOST)
        
        # 연결 테스트
        if not ES.ping():
            print("⚠️  Warning: Elasticsearch 서버에 연결할 수 없습니다.")
            print("   Elasticsearch 기능이 비활성화됩니다.")
            ES = None
        else:
            # 인덱스 존재 확인
            if not ES.indices.exists(index=settings.ES_INDEX):
                print(f"⚠️  Warning: Elasticsearch 인덱스 '{settings.ES_INDEX}'가 존재하지 않습니다.")
                print(f"   인덱스를 생성하려면 다음 명령을 실행하세요:")
                print(f"   python scripts/index_elasticsearch.py")
                print("   Elasticsearch 기능이 비활성화됩니다.")
                ES = None
            else:
                count = ES.count(index=settings.ES_INDEX)["count"]
                print(f"✓ Elasticsearch 연결 성공: {count}개 문서 색인됨")
    except Exception as e:
        print(f"⚠️  Warning: Elasticsearch 연결 실패: {e}")
        print("   Elasticsearch 기능이 비활성화됩니다.")
        ES = None

def embed_texts(texts, is_query=False):
    """
    텍스트를 임베딩 벡터로 변환
    
    Args:
        texts: 단일 문자열 또는 문자열 리스트
        is_query: True면 쿼리용 인코딩, False면 문서 인코딩
    """
    # 설정에 따라 인코딩 방식 결정
    if settings.EMB_ENCODING_MODE == "unified":
        # 인덱스 구축 시 encode를 사용한 경우, 쿼리도 encode 사용
        return MODEL.encode(
            texts, 
            convert_to_numpy=True, 
            show_progress_bar=False, 
            normalize_embeddings=True
        )
    else:
        # 기본: 쿼리는 encode_query, 문서는 encode (BGE-M3 권장 방식)
        if is_query:
            return MODEL.encode_query(
                texts, 
                convert_to_numpy=True, 
                show_progress_bar=False, 
                normalize_embeddings=True
            )
        else:
            return MODEL.encode(
                texts, 
                convert_to_numpy=True, 
                show_progress_bar=False, 
                normalize_embeddings=True
            )

# =======================================
# Phi-3 Embedding (Intent Classification)
# =======================================

PHI3_MODEL = None
PHI3_TOKENIZER = None

if PHI3_AVAILABLE:
    print("📦 Loading Phi-3 embedding model...")
    try:
        # Phi-3는 CausalLM 모델이므로 AutoModelForCausalLM 사용
        from transformers import AutoModelForCausalLM
        
        PHI3_MODEL = AutoModelForCausalLM.from_pretrained(
            settings.PHI3_MODEL_NAME,
            dtype=torch.float32,
            trust_remote_code=True
        )
        PHI3_TOKENIZER = AutoTokenizer.from_pretrained(
            settings.PHI3_MODEL_NAME,
            trust_remote_code=True
        )
        
        # 모델을 평가 모드로 설정
        PHI3_MODEL.eval()
        
        # 모델의 hidden_size 확인
        if hasattr(PHI3_MODEL.config, 'hidden_size'):
            actual_hidden_size = PHI3_MODEL.config.hidden_size
            print(f"✓ Phi-3 model loaded: {settings.PHI3_MODEL_NAME}")
            print(f"✓ Model hidden_size: {actual_hidden_size}")
            if actual_hidden_size != settings.PHI3_EMBEDDING_DIM:
                print(f"⚠️  Warning: 설정된 임베딩 차원({settings.PHI3_EMBEDDING_DIM})과 모델 hidden_size({actual_hidden_size})가 다릅니다.")
        else:
            print(f"✓ Phi-3 model loaded: {settings.PHI3_MODEL_NAME}")
    except Exception as e:
        print(f"⚠️  Warning: Phi-3 model loading failed: {e}")
        print("   Phi-3 embedding 기능이 비활성화됩니다.")
        PHI3_MODEL = None
        PHI3_TOKENIZER = None

def get_phi3_embedding(text: str) -> np.ndarray:
    """
    텍스트를 Phi-3 임베딩 벡터로 변환 (3072차원)
    
    Args:
        text: 입력 텍스트
        
    Returns:
        3072차원 numpy 배열 (Float32)
    """
    if not PHI3_AVAILABLE or PHI3_MODEL is None or PHI3_TOKENIZER is None:
        raise RuntimeError("Phi-3 모델이 로드되지 않았습니다. transformers와 torch가 설치되어 있는지 확인하세요.")
    
    # 토크나이징
    inputs = PHI3_TOKENIZER(
        text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512
    )
    
    # GPU 사용 가능시 GPU로 이동
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    PHI3_MODEL.to(device)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    # Forward pass
    with torch.no_grad():
        # use_cache=False로 설정하여 cache 관련 오류 방지
        outputs = PHI3_MODEL(**inputs, use_cache=False, output_hidden_states=True)
        
        # 임베딩 추출: 마지막 hidden state의 평균 풀링
        # shape: [batch_size, seq_len, hidden_size]
        # output_hidden_states=True이면 hidden_states가 있음
        if hasattr(outputs, 'hidden_states') and outputs.hidden_states is not None:
            # 마지막 레이어의 hidden state 사용
            hidden_states = outputs.hidden_states[-1]
        else:
            # last_hidden_state 사용 (기본)
            hidden_states = outputs.last_hidden_state
        
        # 평균 풀링 (mean pooling)
        # attention_mask 고려
        attention_mask = inputs.get("attention_mask", None)
        if attention_mask is not None:
            # attention_mask를 확장하여 hidden_states와 같은 차원으로 만듦
            mask_expanded = attention_mask.unsqueeze(-1).expand(hidden_states.size()).float()
            # 마스크된 토큰은 0으로 처리
            sum_hidden = torch.sum(hidden_states * mask_expanded, dim=1)
            sum_mask = torch.clamp(mask_expanded.sum(dim=1), min=1e-9)
            embedding = sum_hidden / sum_mask
        else:
            # attention_mask가 없으면 평균 풀링
            embedding = torch.mean(hidden_states, dim=1)
        
        # CPU로 이동하고 numpy로 변환
        embedding = embedding.cpu().numpy().astype(np.float32)
        
        # 차원 확인 및 조정 (3072차원으로 정규화)
        current_dim = embedding.shape[1]
        if current_dim != settings.PHI3_EMBEDDING_DIM:
            if current_dim < settings.PHI3_EMBEDDING_DIM:
                # 패딩 추가 (0으로 채움)
                padding = np.zeros((embedding.shape[0], settings.PHI3_EMBEDDING_DIM - current_dim), dtype=np.float32)
                embedding = np.concatenate([embedding, padding], axis=1)
            elif current_dim > settings.PHI3_EMBEDDING_DIM:
                # 잘라내기
                embedding = embedding[:, :settings.PHI3_EMBEDDING_DIM]
        
        # 1차원 배열로 변환 (단일 텍스트 입력 가정)
        return embedding[0]
