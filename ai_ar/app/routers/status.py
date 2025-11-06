from fastapi import APIRouter

router = APIRouter(prefix="/status", tags=["Status"])

@router.get("/health")
def health_check():
    return {"status": "ok", "message": "FastAPI server running"}
