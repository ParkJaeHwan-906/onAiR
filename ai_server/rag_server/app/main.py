# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat_router, embedding_router, tts_router

app = FastAPI(title="RAG FastAPI Server")

# CORS 미들웨어 설정 (웹 브라우저에서 접근 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 Origin 허용 (프로덕션에서는 특정 도메인만 지정 권장)
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, PUT, DELETE 등 모든 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# RAG Chat 엔드포인트 (Answerability + Generator + Self-Score)
# chat_router는 이미 prefix="/rag"를 가지고 있음
app.include_router(chat_router.router)

# Phi-3 Embedding 엔드포인트 (Intent Classification)
# embedding_router는 prefix="/api"를 가지고 있음
app.include_router(embedding_router.router)

# TTS 엔드포인트 (Text-to-Speech)
# tts_router는 prefix="/api"를 가지고 있음
app.include_router(tts_router.router)

@app.get("/")
def root():
    return {
        "message": "RAG Server is running 🚀",
        "endpoints": {
            "rag_chat": "/rag/chat",
            "embedding": "/api/embedding",
            "tts": "/api/tts",
            "docs": "/docs"
        }
    }
