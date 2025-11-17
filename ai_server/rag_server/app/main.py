# app/main.py
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import tts_router, cv_rag_router
from app.sockets.socket_handler import init_socketio, sio
from app.core.config import settings

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

# TTS 엔드포인트 (Text-to-Speech)
# tts_router는 prefix="/api"를 가지고 있음
app.include_router(tts_router.router)

# CV RAG 엔드포인트 (YOLO 탐지 결과 기반 RAG 답변 생성)
# 실제 서비스 로직을 재사용하는 HTTP 엔드포인트 (Postman 테스트용)
app.include_router(cv_rag_router.router)

# 주의: 실제 서비스는 Socket.IO를 통해 통신합니다.
# - RAG Chat: Socket.IO 이벤트로 처리 (socket_handler.py)
# - STT: Socket.IO 이벤트로 처리 (socket_handler.py)
# - Clarify: Socket.IO 이벤트로 처리 (socket_handler.py)
# - AR 마커: Socket.IO 이벤트로 처리 (socket_handler.py)

@app.get("/")
def root():
    return {
        "message": "RAG Server is running 🚀",
        "endpoints": {
            "tts": "/api/tts",
            "cv_rag": "/api/cv/rag",
            "docs": "/docs"
        },
        "socketio": {
            "enabled": USE_SOCKETIO,
            "path": "/ws",
            "note": "실제 서비스는 Socket.IO를 통해 통신합니다. (socket_handler.py)",
            "events": [
                "stt_result (STT 결과 수신)",
                "intent_audio_completed (Intent 음성 재생 완료)",
                "audio_playback_completed (오디오 재생 완료)",
                "clarify_turn (Clarify 턴)",
                "final_answer (최종 답변)",
                "cv_detection_failed (CV 탐지 실패)",
                "cv_detection_normal (CV 탐지 정상)",
                "wakeword_detected (Wakeword 감지)",
                "ar-marker (AR 마커 생성)",
                "video_frame (비디오 프레임)"
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

# 서버 실행 방법:
# 1. uvicorn 사용 (권장):
#    uvicorn app.main:asgi_app --host {settings.FASTAPI_SERVER_HOST} --port {settings.FASTAPI_SERVER_PORT} --reload
#
# 2. Python으로 직접 실행:
#    import uvicorn
#    from app.core.config import settings
#    uvicorn.run("app.main:asgi_app", host=settings.FASTAPI_SERVER_HOST, port=settings.FASTAPI_SERVER_PORT, reload=True)
#
# 설정 파일: app/core/config.py
# - FASTAPI_SERVER_URL: 모바일 앱에서 접근할 URL (예: "http://192.168.0.100:8000")
# - FASTAPI_SERVER_HOST: 서버 바인딩 호스트 (기본값: "0.0.0.0")
# - FASTAPI_SERVER_PORT: 서버 포트 (기본값: 8000)
