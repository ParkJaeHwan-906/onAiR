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

# Phi-3 관련 코드 제거됨 (Gemini-Flash로 Intent 분류 대체)

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
        # encode_query가 없으면 encode 사용 (fallback)
        if is_query:
            if hasattr(MODEL, 'encode_query'):
                return MODEL.encode_query(
                    texts, 
                    convert_to_numpy=True, 
                    show_progress_bar=False, 
                    normalize_embeddings=True
                )
            else:
                # encode_query가 없는 경우 encode 사용
                return MODEL.encode(
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

# Phi-3 및 경량 임베딩 모델 관련 코드 제거됨
# Intent 분류는 이제 Gemini-Flash를 사용합니다 (app/services/intent_service.py)
