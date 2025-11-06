"""
GCP TTS (Text-to-Speech) 서비스

텍스트를 받아서 GCP TTS를 사용하여 음성 파일로 변환합니다.
"""
import os
import base64
from pathlib import Path
from typing import Optional
from app.core.config import settings

# GCP TTS 클라이언트
try:
    from google.cloud import texttospeech
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    texttospeech = None

# TTS 클라이언트 초기화
_tts_client: Optional[texttospeech.TextToSpeechClient] = None


def _get_tts_client() -> Optional[texttospeech.TextToSpeechClient]:
    """GCP TTS 클라이언트 초기화 및 반환"""
    global _tts_client
    
    if not TTS_AVAILABLE:
        return None
    
    if _tts_client is None:
        try:
            # 서비스 계정 키 파일 경로 설정
            if settings.GCP_TTS_CREDENTIALS_PATH:
                credentials_path = settings.GCP_TTS_CREDENTIALS_PATH
                
                # 상대 경로인 경우 프로젝트 루트 기준으로 변환
                if not os.path.isabs(credentials_path):
                    # 프로젝트 루트 디렉토리 찾기 (app/services/tts_service.py 기준)
                    project_root = Path(__file__).parent.parent.parent
                    credentials_path = str(project_root / credentials_path)
                
                # 파일 존재 확인
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"GCP TTS 서비스 계정 키 파일을 찾을 수 없습니다: {credentials_path}\n"
                        f"   credentials/ 폴더에 JSON 키 파일을 배치하고 .env 파일에 경로를 설정하세요."
                    )
                
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            
            _tts_client = texttospeech.TextToSpeechClient()
            print("✓ GCP TTS 클라이언트 초기화 완료")
        except Exception as e:
            print(f"⚠️  Warning: GCP TTS 클라이언트 초기화 실패: {e}")
            print("   TTS 기능이 비활성화됩니다.")
            return None
    
    return _tts_client


def text_to_speech(text: str, 
                   voice_name: Optional[str] = None,
                   language_code: Optional[str] = None,
                   audio_encoding: Optional[str] = None) -> dict:
    """
    텍스트를 음성 파일로 변환
    
    Args:
        text: 변환할 텍스트
        voice_name: 음성 이름 (기본값: settings.GCP_TTS_VOICE_NAME)
        language_code: 언어 코드 (기본값: settings.GCP_TTS_LANGUAGE_CODE)
        audio_encoding: 오디오 인코딩 형식 (기본값: settings.GCP_TTS_AUDIO_ENCODING)
    
    Returns:
        {
            "audio_content": base64 인코딩된 오디오 데이터,
            "audio_encoding": 오디오 인코딩 형식,
            "mime_type": MIME 타입
        }
    """
    client = _get_tts_client()
    
    if not client:
        raise RuntimeError("GCP TTS 클라이언트가 초기화되지 않았습니다. GCP 서비스 계정 키를 확인하세요.")
    
    if not text or not text.strip():
        raise ValueError("텍스트가 비어있습니다.")
    
    # 기본값 사용
    voice_name = voice_name or settings.GCP_TTS_VOICE_NAME
    language_code = language_code or settings.GCP_TTS_LANGUAGE_CODE
    audio_encoding = audio_encoding or settings.GCP_TTS_AUDIO_ENCODING
    
    # 음성 설정
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
    )
    
    # 오디오 설정
    audio_config = texttospeech.AudioConfig(
        audio_encoding=getattr(texttospeech.AudioEncoding, audio_encoding),
    )
    
    # 합성 요청
    synthesis_input = texttospeech.SynthesisInput(text=text.strip())
    
    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Base64 인코딩
        audio_base64 = base64.b64encode(response.audio_content).decode('utf-8')
        
        # MIME 타입 결정
        mime_types = {
            "MP3": "audio/mpeg",
            "LINEAR16": "audio/wav",
            "OGG_OPUS": "audio/ogg",
        }
        mime_type = mime_types.get(audio_encoding, "audio/mpeg")
        
        return {
            "audio_content": audio_base64,
            "audio_encoding": audio_encoding,
            "mime_type": mime_type,
            "text_length": len(text),
        }
        
    except Exception as e:
        raise RuntimeError(f"TTS 합성 실패: {str(e)}")

