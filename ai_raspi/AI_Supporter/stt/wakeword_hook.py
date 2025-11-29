# 🧩 wakeword_hook.py
# Wakeword 감지 모듈 래퍼

#from .wakeword_detector import WakewordDetector
from .wakeup import WakewordDetector

# 전역 감지기 인스턴스
_detector = None

def init_wakeword_detector(model_path=None):
    """
    Wakeword 감지기 초기화 (시작은 하지 않음)
    
    Args:
        model_path: TFLite 모델 경로 (None이면 기본 경로 사용)
    
    Note:
        start()는 stt_core.py에서 명시적으로 호출됩니다.
    """
    global _detector
    if _detector is None:
        _detector = WakewordDetector(model_path)
        # start()는 stt_core.py에서 명시적으로 호출하므로 여기서는 호출하지 않음
    return _detector

def wait_for_wakeword(timeout=None):
    """
    Wakeword 감지 대기
    
    Args:
        timeout: 대기 시간 (초), None이면 무한 대기
    
    Returns:
        bool: Wakeword 감지 시 True
    """
    global _detector
    if _detector is None:
        # 초기화되지 않은 경우 자동 초기화
        _detector = init_wakeword_detector()
    
    return _detector.wait_for_wakeword(timeout)

def stop_wakeword_detector():
    """Wakeword 감지기 중지"""
    global _detector
    if _detector:
        _detector.stop()
        _detector = None
