# app/services/answerability.py
"""
RAG 검색 관련 유틸리티 함수
"""
from typing import List, Dict, Any


def normalize_query_style(query: str) -> str:
    """
    문체 정규화: retrieval 전에 적용하여 검색 품질 향상
    
    공조기 매뉴얼 문체로 정규화하여 검색 정확도를 높입니다.
    """
    normalized = query
    replacements = {
        "않습니다": "안 됩니다",
        "않아": "안 돼요",
        "되지 않": "안 되",
        "않고": "안 하고",
        "않는": "안 되는",
        "않으면": "안 되면",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized


