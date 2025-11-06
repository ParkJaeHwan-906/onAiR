# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat_router, embedding_router, tts_router, stt_router, clarify_router, ar_process

# Socket.IO 통합을 위해 ai_ar의 socket_manager 사용
try:
    import sys
    import os
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # ai_server/rag_server/app/main.py -> ai_server/rag_server -> ai_server -> S13P31A407
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_dir)))
    ai_ar_path = os.path.join(project_root, "ai_ar")
    
    print(f"🔍 디버깅: current_file_dir = {current_file_dir}")
    print(f"🔍 디버깅: project_root = {project_root}")
    print(f"🔍 디버깅: ai_ar_path = {ai_ar_path}")
    print(f"🔍 디버깅: ai_ar_path 존재 여부 = {os.path.exists(ai_ar_path)}")
    
    if os.path.exists(ai_ar_path):
        # ai_ar/app을 sys.path에 추가해야 app 모듈을 찾을 수 있음
        ai_ar_app_path = os.path.join(ai_ar_path, "app")
        if os.path.exists(ai_ar_app_path):
            # ai_ar/app을 sys.path에 추가 (이렇게 하면 from sockets.socket_manager로 import 가능)
            if ai_ar_app_path not in sys.path:
                sys.path.insert(0, ai_ar_app_path)
                print(f"✅ ai_ar_app_path를 sys.path에 추가했습니다: {ai_ar_app_path}")
        else:
            print(f"⚠️ ai_ar/app 경로를 찾을 수 없습니다: {ai_ar_app_path}")
    
    import socketio
    print(f"✅ socketio 모듈 import 성공")
    
    # ai_ar/app을 sys.path에 추가했으므로 sockets.socket_manager로 import
    # socket_manager를 import하면 모든 이벤트 핸들러(@sio.on)가 자동으로 등록됨
    import sockets.socket_manager as socket_manager_module
    from sockets.socket_manager import sio
    print(f"✅ socket_manager.sio import 성공")
    print(f"✅ Socket.IO 이벤트 핸들러 등록 완료")
    
    USE_SOCKETIO = True
    print(f"✅ Socket.IO 통합 활성화됨")
except ImportError as e:
    print(f"⚠️ Socket.IO를 사용할 수 없습니다. HTTP 엔드포인트만 사용합니다.")
    print(f"   ImportError: {e}")
    import traceback
    traceback.print_exc()
    USE_SOCKETIO = False
    sio = None
except Exception as e:
    print(f"⚠️ Socket.IO 통합 중 오류 발생: {e}")
    import traceback
    traceback.print_exc()
    USE_SOCKETIO = False
    sio = None

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
            "embedding": "/api/embedding",
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
else:
    # Socket.IO 없이 FastAPI만 사용
    asgi_app = app

# uvicorn 실행 시: uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000
