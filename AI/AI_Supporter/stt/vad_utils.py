import webrtcvad
from config import settings

vad = webrtcvad.Vad(2)  # 0~3, 높을수록 민감

def has_voice(frame: bytes) -> bool:
    """frame에서 음성이 존재하는지 검사"""
    frame_ms = 30
    step = int(settings.RATE * frame_ms / 1000) * 2
    for i in range(0, len(frame), step):
        sub = frame[i:i + step]
        if len(sub) < step:
            break
        if vad.is_speech(sub, settings.RATE):
            return True
    return False
