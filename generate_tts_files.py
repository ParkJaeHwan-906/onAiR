"""
GCP TTS를 사용하여 음성 파일 생성 스크립트

사용법:
1. GCP 서비스 계정 키 파일 경로 설정 (GCP_CREDENTIALS_PATH)
2. 텍스트 리스트에 변환할 텍스트 입력
3. 실행: python generate_tts_files.py

생성된 파일은 output/ 폴더에 저장됩니다.
"""
import os
import base64
from pathlib import Path
from google.cloud import texttospeech

# ========================================
# 설정
# ========================================
# GCP 서비스 계정 키 파일 경로 (상대 경로 또는 절대 경로)
# 상대 경로인 경우 프로젝트 루트 기준
# 예: "ai_server/rag_server/credentials/gcp-tts-key.json" 또는 절대 경로
GCP_CREDENTIALS_PATH = 'C:\\Users\\SSAFY\\Documents\\S13P31A407\\ai_server\\rag_server\\credentials\\tts-key.json'  # 실제 키 파일명으로 수정 필요

# 음성 설정
VOICE_NAME = "ko-KR-Standard-A"  # 한국어 여성 음성
LANGUAGE_CODE = "ko-KR"
AUDIO_ENCODING = "MP3"  # MP3, LINEAR16, OGG_OPUS

# 출력 폴더
OUTPUT_DIR = "output"

# 모바일 앱 assets 폴더 경로 (상대 경로)
MOBILE_ASSETS_DIR = "mobile/app/src/main/assets"

# ========================================
# 변환할 텍스트 리스트
# ========================================
TEXTS = [
    "AI Supporter 기능을 시작합니다. 오류 탐지 중이니 움직이지 말아주세요."
]

# ========================================
# TTS 클라이언트 초기화
# ========================================
def init_tts_client():
    """GCP TTS 클라이언트 초기화"""
    # 서비스 계정 키 파일 경로 확인
    if not os.path.isabs(GCP_CREDENTIALS_PATH):
        # 상대 경로인 경우 프로젝트 루트 기준으로 변환
        script_dir = Path(__file__).parent  # 프로젝트 루트
        credentials_path = script_dir / GCP_CREDENTIALS_PATH
    else:
        credentials_path = Path(GCP_CREDENTIALS_PATH)
    
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"GCP 서비스 계정 키 파일을 찾을 수 없습니다: {credentials_path}\n"
            f"   GCP_CREDENTIALS_PATH를 올바른 경로로 설정하세요."
        )
    
    # 환경 변수 설정
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)
    
    # TTS 클라이언트 생성
    client = texttospeech.TextToSpeechClient()
    print(f"✅ GCP TTS 클라이언트 초기화 완료")
    print(f"   서비스 계정 키: {credentials_path}")
    
    return client

# ========================================
# 텍스트를 음성 파일로 변환
# ========================================
def text_to_audio_file(client, text: str, output_path: str):
    """
    텍스트를 음성 파일로 변환하여 저장
    
    Args:
        client: GCP TTS 클라이언트
        text: 변환할 텍스트
        output_path: 저장할 파일 경로
    """
    # 음성 설정
    voice = texttospeech.VoiceSelectionParams(
        language_code=LANGUAGE_CODE,
        name=VOICE_NAME,
    )
    
    # 오디오 설정
    audio_config = texttospeech.AudioConfig(
        audio_encoding=getattr(texttospeech.AudioEncoding, AUDIO_ENCODING),
    )
    
    # 합성 요청
    synthesis_input = texttospeech.SynthesisInput(text=text.strip())
    
    try:
        print(f"📝 변환 중: '{text[:50]}...'")
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # 파일 저장
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(response.audio_content)
        
        file_size = len(response.audio_content)
        print(f"✅ 저장 완료: {output_path} ({file_size:,} bytes)")
        
    except Exception as e:
        print(f"❌ 변환 실패: {e}")
        raise

# ========================================
# 메인 함수
# ========================================
def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🎤 GCP TTS 음성 파일 생성 스크립트")
    print("=" * 60)
    
    # 출력 폴더 생성
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 출력 폴더: {output_dir.absolute()}")
    print()
    
    # TTS 클라이언트 초기화
    try:
        client = init_tts_client()
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        return
    
    print()
    print("=" * 60)
    print(f"📝 변환할 텍스트 개수: {len(TEXTS)}개")
    print("=" * 60)
    print()
    
    # 각 텍스트를 음성 파일로 변환
    success_count = 0
    for idx, text in enumerate(TEXTS, 1):
        try:
            # 파일명 생성 (텍스트의 처음 30자 사용, 특수문자 제거)
            safe_text = "".join(c for c in text[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_text = safe_text.replace(' ', '_')
            if not safe_text:
                safe_text = f"audio_{idx}"
            
            # 파일 확장자 결정
            extensions = {
                "MP3": ".mp3"
            }
            extension = extensions.get(AUDIO_ENCODING, ".mp3")
            
            # 출력 파일 경로
            output_path = output_dir / f"{idx:03d}_{safe_text}{extension}"
            
            # 변환 및 저장
            text_to_audio_file(client, text, output_path)
            success_count += 1
            
        except Exception as e:
            print(f"⚠️  텍스트 {idx} 변환 실패: {e}")
            continue
        
        print()
    
    # 결과 요약
    print("=" * 60)
    print(f"✅ 완료: {success_count}/{len(TEXTS)}개 파일 생성 성공")
    print(f"📁 저장 위치: {output_dir.absolute()}")
    print("=" * 60)
    
    # 모바일 앱 assets 폴더로 파일 복사
    print()
    print("=" * 60)
    print("📦 모바일 앱 assets 폴더로 파일 복사 중...")
    print("=" * 60)
    
    try:
        # 프로젝트 루트 디렉토리 찾기 (스크립트 위치 기준)
        script_dir = Path(__file__).parent
        mobile_assets_dir = script_dir / MOBILE_ASSETS_DIR
        mobile_assets_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 모바일 assets 폴더: {mobile_assets_dir.absolute()}")
        
        # 생성된 모든 파일을 assets 폴더로 복사
        copied_count = 0
        for idx, text in enumerate(TEXTS, 1):
            try:
                # 파일명 생성 (텍스트의 처음 30자 사용, 특수문자 제거)
                safe_text = "".join(c for c in text[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_text = safe_text.replace(' ', '_')
                if not safe_text:
                    safe_text = f"audio_{idx}"
                
                # 파일 확장자 결정
                extensions = {
                    "MP3": ".mp3",
                    "LINEAR16": ".wav",
                    "OGG_OPUS": ".ogg",
                }
                extension = extensions.get(AUDIO_ENCODING, ".mp3")
                
                # 원본 파일 경로
                source_file = output_dir / f"{idx:03d}_{safe_text}{extension}"
                
                # 대상 파일 경로 (assets 폴더)
                dest_file = mobile_assets_dir / f"{idx:03d}_{safe_text}{extension}"
                
                if source_file.exists():
                    import shutil
                    shutil.copy2(source_file, dest_file)
                    print(f"✅ 복사 완료: {dest_file.name}")
                    copied_count += 1
                else:
                    print(f"⚠️  파일 없음: {source_file.name}")
            except Exception as e:
                print(f"⚠️  파일 복사 실패 ({idx}): {e}")
                continue
        
        print("=" * 60)
        print(f"✅ 복사 완료: {copied_count}/{success_count}개 파일을 assets 폴더로 복사")
        print(f"📁 모바일 assets 위치: {mobile_assets_dir.absolute()}")
        print("=" * 60)
        print()
        print("💡 이제 모바일 앱을 빌드하면 오디오 파일이 APK에 포함됩니다!")
        print("=" * 60)
        
    except Exception as e:
        print(f"⚠️  모바일 assets 폴더 복사 실패: {e}")
        print("   수동으로 output/ 폴더의 파일을 mobile/app/src/main/assets/ 폴더로 복사하세요.")
        print("=" * 60)

if __name__ == "__main__":
    main()

