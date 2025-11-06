"""
빠른 통합 테스트 스크립트
최소한의 설정으로 전체 시스템을 빠르게 테스트할 수 있습니다.
"""
import sys
import os
import time

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def check_dependencies():
    """필수 패키지 확인"""
    print_section("📦 의존성 확인")
    
    required = ['fastapi', 'uvicorn', 'pyaudio', 'sounddevice']
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} (설치 필요)")
            missing.append(pkg)
    
    if missing:
        print(f"\n⚠️  다음 패키지를 설치하세요:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    return True

def check_env_file():
    """환경 변수 파일 확인"""
    print_section("⚙️  환경 설정 확인")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, '.env')
    
    if not os.path.exists(env_path):
        print("⚠️  .env 파일이 없습니다.")
        print("   기본 설정으로 진행합니다.")
        return False
    
    print("✅ .env 파일 발견")
    return True

def check_gcp_key():
    """GCP 인증 키 확인"""
    print_section("🔑 GCP 인증 키 확인")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key_path = os.path.join(base_dir, "secrets", "stt-key.json")
    
    if os.path.exists(key_path):
        print(f"✅ GCP 인증 키 발견: {key_path}")
        return True
    else:
        print(f"⚠️  GCP 인증 키 없음: {key_path}")
        print("   STT 테스트는 건너뜁니다.")
        return False

def print_test_instructions():
    """테스트 방법 안내"""
    print_section("🧪 테스트 방법")
    
    print("""
1️⃣  개별 모듈 테스트:
   python tests/test_modules.py

2️⃣  WebSocket 클라이언트 테스트 (별도 터미널):
   python tests/test_websocket_client.py

3️⃣  전체 시스템 테스트:
   - 터미널 1: python tests/test_websocket_client.py
   - 터미널 2: python main.py
   
   그 다음 "onAir"라고 말하면 전체 흐름이 실행됩니다!

📖 자세한 내용은 tests/TEST_GUIDE.md를 참고하세요.
    """)

def main():
    print_section("🚀 빠른 테스트 시작")
    
    # 의존성 확인
    if not check_dependencies():
        print("\n❌ 의존성 확인 실패. 테스트를 중단합니다.")
        return
    
    # 환경 설정 확인
    check_env_file()
    
    # GCP 키 확인
    has_gcp = check_gcp_key()
    
    # 테스트 방법 안내
    print_test_instructions()
    
    # 간단한 모듈 테스트 제안
    print_section("💡 빠른 테스트 제안")
    print("지금 바로 테스트하려면:")
    print("  python tests/test_modules.py")
    print("\n또는 전체 시스템을 실행하려면:")
    print("  python main.py")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 종료")

