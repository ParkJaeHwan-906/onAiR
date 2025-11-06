# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat_router, embedding_router, tts_router, stt_router, clarify_router

# FastAPI 앱 생성
app = FastAPI(title="RAG FastAPI Server")

# CORS 미들웨어 설정 (웹 브라우저에서 접근 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 Origin 허용 (프로덕션에서는 특정 도메인만 지정 권장)
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, PUT, DELETE 등 모든 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# 참고: Socket.IO 서버는 ai_ar 프로젝트의 socket_manager.py를 사용합니다.
# FastAPI는 HTTP 엔드포인트만 제공하며, socket_manager가 FastAPI를 호출합니다.

# RAG Chat 엔드포인트 (Answerability + Generator + Self-Score)
# chat_router는 이미 prefix="/rag"를 가지고 있음
app.include_router(chat_router.router)

# Phi-3 Embedding 엔드포인트 (Intent Classification)
# embedding_router는 prefix="/api"를 가지고 있음
app.include_router(embedding_router.router)

# TTS 엔드포인트 (Text-to-Speech)
# tts_router는 prefix="/api"를 가지고 있음
app.include_router(tts_router.router)

# STT 엔드포인트 (Speech-to-Text 버퍼링 결과 수신)
# stt_router는 prefix="/api/stt"를 가지고 있음
app.include_router(stt_router.router)

# Clarify 엔드포인트 (Clarify 처리)
# clarify_router는 prefix="/api/clarify"를 가지고 있음
app.include_router(clarify_router.router)

@app.get("/")
def root():
    return {
        "message": "RAG Server is running 🚀",
        "endpoints": {
            "rag_chat": "/rag/chat",
            "embedding": "/api/embedding",
            "tts": "/api/tts",
            "stt_buffered": "/api/stt/buffered",
            "clarify_streaming": "/api/clarify/streaming",
            "clarify_process": "/api/clarify/process",
            "clarify_response": "/api/clarify/response",
            "docs": "/docs"
        },
        "socketio": {
            "note": "Socket.IO 서버는 ai_ar 프로젝트의 socket_manager.py를 사용합니다.",
            "fastapi_endpoints": [
                "/api/stt/buffered (버퍼링 STT 수신)",
                "/api/stt/streaming (Streaming STT 수신)",
                "/api/clarify/process (Clarify 처리)",
                "/api/clarify/response (Clarify 응답 수신)"
            ]
        }
    }

# uvicorn 실행 시: uvicorn app.main:app --host 0.0.0.0 --port 8000
