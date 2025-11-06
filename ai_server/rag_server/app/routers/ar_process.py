from fastapi import APIRouter, File, UploadFile
import cv2
import numpy as np

router = APIRouter(prefix="/ar", tags=["AR"])

@router.post("/analyze")
async def analyze_frame(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(300)
    kp = orb.detect(gray, None)
    kp, des = orb.compute(gray, kp)

    return {"keypoints": len(kp), "message": "Frame analyzed successfully"}
