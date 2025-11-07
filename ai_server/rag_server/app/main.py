# app/main.py
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from app.routers import chat_router, embedding_router, tts_router, stt_router, clarify_router, ar_process
from app.routers import chat_router, tts_router, stt_router, clarify_router, ar_process
from app.sockets.socket_handler import init_socketio, sio

USE_SOCKETIO = True

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

# Socket.IO 초기화 (app 생성 후 바로)
if USE_SOCKETIO:
    init_socketio()  # 이벤트 핸들러 등록
    print("✅ Socket.IO 초기화 완료")

# RAG Chat 엔드포인트 (Answerability + Generator + Self-Score)
# chat_router는 이미 prefix="/rag"를 가지고 있음
app.include_router(chat_router.router)

# Embedding 엔드포인트 제거됨 (Gemini-Flash로 Intent 분류 대체)

# TTS 엔드포인트 (Text-to-Speech)
# tts_router는 prefix="/api"를 가지고 있음
app.include_router(tts_router.router)

# STT 엔드포인트 (Speech-to-Text 버퍼링 결과 수신)
# stt_router는 prefix="/api/stt"를 가지고 있음
app.include_router(stt_router.router)

# Clarify 엔드포인트 (Clarify 처리)
# clarify_router는 prefix="/api/clarify"를 가지고 있음
app.include_router(clarify_router.router)

# AR 마커 엔드포인트
# ar_process는 prefix="/ar"를 가지고 있음
# 마완성
app.include_router(ar_process.router)

@app.get("/")
def root():
    return {
        "message": "RAG Server is running 🚀",
        "endpoints": {
            "rag_chat": "/rag/chat",
            "tts": "/api/tts",
            "stt_buffered": "/api/stt/buffered",
            "clarify_streaming": "/api/clarify/streaming",
            "clarify_process": "/api/clarify/process",
            "clarify_response": "/api/clarify/response",
            "docs": "/docs"
        },
        "socketio": {
            "enabled": USE_SOCKETIO,
            "note": "Socket.IO 서버는 ai_ar 프로젝트의 socket_manager.py를 사용합니다." if USE_SOCKETIO else "Socket.IO를 사용할 수 없습니다.",
            "fastapi_endpoints": [
                "/api/stt/buffered (버퍼링 STT 수신)",
                "/api/stt/streaming (Streaming STT 수신)",
                "/api/clarify/process (Clarify 처리)",
                "/api/clarify/response (Clarify 응답 수신)"
            ]
        }
    }

# Socket.IO 통합 (ai_ar의 socket_manager 사용)
if USE_SOCKETIO:
    asgi_app = socketio.ASGIApp(
        sio,
        other_asgi_app=app,
        socketio_path="/ws"
    )
    print(f"✅ Socket.IO ASGIApp 설정 완료 (path=/ws)")
else:
    # Socket.IO 없이 FastAPI만 사용
    asgi_app = app
    print("⚠️ Socket.IO 없이 FastAPI만 사용")

# uvicorn 실행 시: uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000
