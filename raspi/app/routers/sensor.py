from fastapi import APIRouter

router = APIRouter(prefix="/sensor", tags=["Sensor"])

@router.get("/")
def get_sensor_data():
    return {"value": 42}
