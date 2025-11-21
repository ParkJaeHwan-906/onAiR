import json
from app.core.config import settings
from app.services.gms_client import call_gemini_via_gms

# ✅ GMS API 키 확인
gms_api_key = settings.GMS_API_KEY if settings.GMS_API_KEY else None


