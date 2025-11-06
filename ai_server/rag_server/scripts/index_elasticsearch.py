"""
Elasticsearch 인덱스 생성 및 데이터 색인 스크립트

사용법:
    python scripts/index_elasticsearch.py

환경 변수:
    ES_HOST: Elasticsearch 서버 주소 (기본값: http://localhost:9200)
    ES_INDEX: 인덱스 이름 (기본값: samkos)
    JSONL_PATH: 데이터 파일 경로 (기본값: app/data/samkos_cleaned.jsonl)
"""
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # tqdm이 없어도 동작하도록
    def tqdm(iterable, *args, **kwargs):
        return iterable

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
except ImportError:
    print("❌ elasticsearch 패키지가 설치되지 않았습니다.")
    print("   pip install elasticsearch 설치 후 다시 실행하세요.")
    sys.exit(1)

from app.core.config import settings


def create_index(es: Elasticsearch, index_name: str) -> None:
    """Elasticsearch 인덱스 생성 (매핑 설정 포함)"""
    
    # 인덱스가 이미 존재하는지 확인
    if es.indices.exists(index=index_name):
        print(f"⚠️  인덱스 '{index_name}'가 이미 존재합니다.")
        response = input("삭제하고 재생성하시겠습니까? (y/N): ")
        if response.lower() == 'y':
            es.indices.delete(index=index_name)
            print(f"✓ 인덱스 '{index_name}' 삭제 완료")
        else:
            print("기존 인덱스를 사용합니다.")
            return
    
    # 인덱스 매핑 설정
    mapping = {
        "mappings": {
            "properties": {
                "content": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "keyword": {
                            "type": "keyword"
                        }
                    }
                },
                "section": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "keyword": {
                            "type": "keyword"
                        }
                    }
                },
                "pages": {
                    "type": "keyword"
                },
                "type": {
                    "type": "keyword"
                },
                "equipment": {
                    "type": "keyword"
                },
                "equipment_name": {
                    "type": "keyword"
                },
                "part": {
                    "type": "keyword"
                },
                "subsection": {
                    "type": "keyword"
                },
                "title": {
                    "type": "text",
                    "analyzer": "standard"
                }
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "korean": {
                        "type": "standard"
                    }
                }
            }
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"✓ 인덱스 '{index_name}' 생성 완료")


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """JSONL 파일 로드"""
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def index_documents(es: Elasticsearch, index_name: str, data: List[Dict[str, Any]], batch_size: int = 1000) -> None:
    """문서를 Elasticsearch에 색인"""
    
    def generate_actions():
        for i, doc in enumerate(data):
            # _id를 명시적으로 설정 (FAISS 인덱스와 동일한 ID 사용)
            doc_id = doc.get("_id", i)
            
            # Elasticsearch에 색인할 문서 구조
            action = {
                "_index": index_name,
                "_id": str(doc_id),
                "_source": {
                    "content": doc.get("content", ""),
                    "section": doc.get("section", ""),
                    "pages": doc.get("pages", ""),
                    "type": doc.get("type", ""),
                    "equipment": doc.get("equipment", ""),
                    "equipment_name": doc.get("equipment_name", ""),
                    "part": doc.get("part", ""),
                    "subsection": doc.get("subsection", ""),
                    "title": doc.get("title", ""),
                }
            }
            yield action
    
    # Bulk 색인
    print(f"📦 {len(data)}개 문서 색인 중...")
    success, failed = bulk(es, generate_actions(), chunk_size=batch_size, request_timeout=60)
    
    print(f"✓ 색인 완료: {success}개 성공")
    if failed:
        print(f"⚠️  실패: {len(failed)}개")
    
    # 인덱스 새로고침
    es.indices.refresh(index=index_name)
    print(f"✓ 인덱스 새로고침 완료")


def main():
    """메인 함수"""
    print("=" * 60)
    print("Elasticsearch 인덱스 생성 및 데이터 색인")
    print("=" * 60)
    
    # Elasticsearch 연결
    es_host = os.getenv("ES_HOST", settings.ES_HOST)
    es_index = os.getenv("ES_INDEX", settings.ES_INDEX)
    jsonl_path = os.getenv("JSONL_PATH", settings.JSONL_PATH)
    
    print(f"\n📋 설정:")
    print(f"   ES_HOST: {es_host}")
    print(f"   ES_INDEX: {es_index}")
    print(f"   JSONL_PATH: {jsonl_path}")
    
    try:
        es = Elasticsearch([es_host])
        # 연결 테스트
        if not es.ping():
            raise Exception("Elasticsearch 서버에 연결할 수 없습니다.")
        print(f"\n✓ Elasticsearch 연결 성공: {es_host}")
    except Exception as e:
        print(f"\n❌ Elasticsearch 연결 실패: {e}")
        print(f"   Elasticsearch 서버가 실행 중인지 확인하세요.")
        sys.exit(1)
    
    # 데이터 로드
    if not os.path.exists(jsonl_path):
        print(f"\n❌ 데이터 파일을 찾을 수 없습니다: {jsonl_path}")
        sys.exit(1)
    
    print(f"\n📖 데이터 파일 로드 중: {jsonl_path}")
    data = load_jsonl(jsonl_path)
    print(f"✓ {len(data)}개 문서 로드 완료")
    
    # 각 문서에 _id 추가 (FAISS 인덱스와 동일하게)
    for i, doc in enumerate(data):
        if "_id" not in doc:
            doc["_id"] = i
    
    # 인덱스 생성
    print(f"\n🔨 인덱스 생성 중: {es_index}")
    create_index(es, es_index)
    
    # 문서 색인
    print(f"\n📝 문서 색인 중...")
    index_documents(es, es_index, data)
    
    # 색인 확인
    count = es.count(index=es_index)["count"]
    print(f"\n✓ 완료! 인덱스 '{es_index}'에 {count}개 문서가 색인되었습니다.")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

