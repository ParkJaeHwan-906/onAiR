from fastapi import APIRouter

router = APIRouter(prefix="/control", tags=["Control"])

@router.get("/")
def get_control_data():
    return {"value": 42}
