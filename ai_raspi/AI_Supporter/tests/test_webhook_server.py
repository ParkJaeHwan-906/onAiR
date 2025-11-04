"""
Webhook 테스트용 간단한 HTTP 서버
앱 서버 대신 webhook 요청을 받아서 확인할 수 있습니다.
"""
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

@app.post("/api/stt/start")
async def stt_start_webhook(request: Request):
    """STT 시작 webhook 엔드포인트"""
    body = await request.json()
    print(f"✅ Webhook 수신: {body}")
    return {"status": "ok", "message": "Webhook received"}

@app.get("/")
async def root():
    return {"message": "Webhook 테스트 서버", "endpoint": "/api/stt/start"}

if __name__ == "__main__":
    print("🌐 Webhook 테스트 서버 시작: http://localhost:8080")
    print("   엔드포인트: POST /api/stt/start")
    uvicorn.run(app, host="0.0.0.0", port=8080)

