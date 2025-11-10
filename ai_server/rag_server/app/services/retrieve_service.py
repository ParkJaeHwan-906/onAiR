import math
import hashlib
import numpy as np
from typing import List, Dict, Any

from app.core.model_loader import DATA, INDEX, ES, CE, embed_texts
from app.core.config import settings

def _fingerprint(s: str) -> str:
    return hashlib.md5(s.strip().encode("utf-8")).hexdigest()

def min_max_normalize(scores: List[float]) -> List[float]:
    if not scores:
        return []
    mn, mx = min(scores), max(scores)
    if math.isclose(mn, mx):
        return [0.5 for _ in scores]
    return [(s - mn) / (mx - mn + 1e-12) for s in scores]

# ---------- Dense (FAISS) ----------
def faiss_search(query: str, top_k: int) -> List[Dict[str, Any]]:
    # BGE-M3: 쿼리는 encode_query 사용
    q_emb = embed_texts([query], is_query=True)
    
    # FAISS 검색을 위해 올바른 shape 확인 (1, dim)
    if q_emb.ndim == 1:
        q_emb = q_emb.reshape(1, -1)
    
    D, I = INDEX.search(q_emb, top_k)
    results = []
    for idx, dist in zip(I[0], D[0]):
        if idx == -1:
            continue
        row = DATA[idx]
        # BGE-M3 + 코사인 유사도 처리:
        # normalize_embeddings=True로 인코딩되어 있으므로:
        # - IndexFlatIP 사용 시: dist는 코사인 유사도 (0~1, 클수록 유사) → 그대로 사용
        # - IndexFlatL2 사용 시: dist는 제곱 거리 (작을수록 유사) → 1 - dist/2로 변환하거나 그냥 -dist 사용
        # 일반적으로 코사인 유사도는 IndexFlatIP 사용을 권장
        # 여기서는 normalize된 벡터이므로 dist 값을 그대로 사용 (IndexFlatIP 기준)
        sim = float(dist)
        results.append({
            "id": row["_id"],
            "channel": "dense",
            "score": sim,
            "source": {
                "pages": row.get("pages"),
                "section": row.get("section"),
                "type": row.get("type"),
                "content": row.get("content")
            }
        })
    return results

# ---------- Sparse (Elastic, optional) ----------
def es_search(query: str, top_k: int) -> List[Dict[str, Any]]:
    if ES is None:
        return []
    body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["section^2", "content"]  # section에 가중치
            }
        }
    }
    resp = ES.search(index=settings.ES_INDEX, body=body)
    hits = []
    for h in resp["hits"]["hits"]:
        src = h["_source"]
        # 가능하면 preprocessing 때 _id를 같이 넣어 ES에 색인하는 것을 권장
        # 여기선 content hash로 id 유사 dedup
        doc_id = src.get("_id") or _fingerprint(src.get("content", "")[:256])
        hits.append({
            "id": doc_id,
            "channel": "sparse",
            "score": float(h["_score"]),
            "source": {
                "pages": src.get("pages"),
                "section": src.get("section"),
                "type": src.get("type"),
                "content": src.get("content")
            }
        })
    return hits

# ---------- Query Expansion ----------
def expand_query(query: str) -> str:
    """
    Query Expansion: 동의어 및 관련어 추가로 검색 품질 향상
    TTS 친화적: 자연스러운 표현으로 확장
    """
    # 설비 유지보수 도메인 특화 동의어 매핑
    synonym_map = {
        "작동 안 함": ["작동하지 않음", "동작 불가", "가동 불가", "운전 불가"],
        "작동 안해": ["작동하지 않음", "동작 불가"],
        "소음": ["소음 발생", "이상 소음", "진동 소음", "소리가 남"],
        "과열": ["온도 상승", "열 발생", "고온", "뜨거워짐"],
        "누수": ["물 새는", "누수 발생", "물 샘", "물이 새요"],
        "회전 안 함": ["회전 불가", "정지", "가동 안 됨", "돌지 않음"],
        "안 돼": ["작동하지 않음", "동작 불가"],
        "안돼": ["작동하지 않음", "동작 불가"],
        "고장": ["작동 불가", "오작동", "이상"],
        "문제": ["이상", "오작동", "고장"],
    }
    
    expanded = query
    for key, synonyms in synonym_map.items():
        if key in query:
            # 상위 2개만 추가 (과도한 확장 방지)
            expanded += " " + " ".join(synonyms[:2])
            break  # 첫 매칭만 적용
    
    return expanded.strip()

# ---------- Hybrid Merge ----------
def hybrid_retrieve(query: str, top_k: int = None, expand: bool = True):
    if top_k is None:
        top_k = settings.TOP_K

    # Query Expansion 적용
    expanded_query = expand_query(query) if expand else query

    dense = faiss_search(expanded_query, top_k)
    sparse = es_search(expanded_query, top_k) if settings.USE_ELASTIC else []

    # 정규화
    dense_norm = min_max_normalize([r["score"] for r in dense])
    for r, s in zip(dense, dense_norm):
        r["dense_norm"] = s

    if sparse:
        sparse_norm = min_max_normalize([r["score"] for r in sparse])
        for r, s in zip(sparse, sparse_norm):
            r["sparse_norm"] = s

    # id 또는 content hash 기준으로 머지
    merged = {}
    def add_or_update(item, dense_part=False, sparse_part=False):
        key = item.get("id") or _fingerprint(item["source"]["content"][:256])
        if key not in merged:
            merged[key] = {
                "id": key,
                "source": item["source"],
                "dense_norm": 0.0,
                "sparse_norm": 0.0
            }
        if dense_part:
            merged[key]["dense_norm"] = item.get("dense_norm", 0.0)
        if sparse_part:
            merged[key]["sparse_norm"] = item.get("sparse_norm", 0.0)

    for d in dense:
        add_or_update(d, dense_part=True)
    for s in sparse:
        add_or_update(s, sparse_part=True)

    alpha = settings.HYBRID_ALPHA
    candidates = []
    for key, v in merged.items():
        hybrid_score = alpha * v["dense_norm"] + (1 - alpha) * v["sparse_norm"]
        candidates.append({
            "id": key,
            "hybrid_score": float(hybrid_score),
            "source": v["source"]
        })

    # hybrid 점수로 1차 정렬
    candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return candidates

# ---------- Rerank ----------
def rerank(query: str, candidates: List[Dict[str, Any]], top_k: int = None):
    if top_k is None:
        top_k = settings.RERANK_TOP_K
    cands = candidates[:max(top_k, 1)]
    if not cands:
        return []

    # 1) CrossEncoder 사용
    if CE is not None:
        pairs = [(query, c["source"]["content"]) for c in cands]
        ce_scores = CE.predict(pairs).tolist()
        # 결합: RERANK_WEIGHT * ce + (1-RERANK_WEIGHT) * hybrid
        rw = settings.RERANK_WEIGHT
        for c, ce in zip(cands, ce_scores):
            c["rerank_score"] = rw * float(ce) + (1 - rw) * float(c["hybrid_score"])
        return sorted(cands, key=lambda x: x["rerank_score"], reverse=True)

    # 2) Fallback: cosine 유사도 (임베딩 재계산)
    q_emb = embed_texts([query], is_query=True)
    q = q_emb[0] if q_emb.ndim == 2 else q_emb
    
    for c in cands:
        v_emb = embed_texts([c["source"]["content"]], is_query=False)
        v = v_emb[0] if v_emb.ndim == 2 else v_emb
        cos = float(np.dot(q, v))  # 이미 normalize된 벡터
        rw = settings.RERANK_WEIGHT
        c["rerank_score"] = rw * cos + (1 - rw) * float(c["hybrid_score"])
    return sorted(cands, key=lambda x: x["rerank_score"], reverse=True)
