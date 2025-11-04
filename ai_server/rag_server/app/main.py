# app/main.py
from fastapi import FastAPI
from app.routers import chat_router

app = FastAPI(title="RAG FastAPI Server")

# RAG Chat 엔드포인트 (Answerability + Generator + Self-Score)
# chat_router는 이미 prefix="/rag"를 가지고 있음
app.include_router(chat_router.router)

@app.get("/")
def root():
    return {"message": "RAG Server is running 🚀"}
