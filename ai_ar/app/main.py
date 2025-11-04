from fastapi import FastAPI

# FastAPI 인스턴스 생성
app = FastAPI(
    title="AI_AR FastAPI Server",
    description="Raspberry Pi + FastAPI + Socket.IO Server",
    version="1.0.0"
)

# Health Check 라우트
@app.get("/")
def read_root():
    return {"message": "Fast API Server is Running"}
