#!/bin/bash
# 라즈베리파이 초기 설정 스크립트

echo "🍓 라즈베리파이 AI Supporter 설정 시작"
echo "========================================"

# 1. 시스템 패키지 업데이트
echo ""
echo "📦 시스템 패키지 업데이트 중..."
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio python3-venv

# 2. 오디오 권한 확인
echo ""
echo "🔊 오디오 권한 확인 중..."
if groups | grep -q audio; then
    echo "✅ audio 그룹에 이미 속해있습니다."
else
    echo "⚠️  audio 그룹 추가 중..."
    sudo usermod -a -G audio $USER
    echo "✅ audio 그룹 추가 완료. 재로그인 후 적용됩니다."
fi

# 3. 마이크 디바이스 확인
echo ""
echo "🎤 마이크 디바이스 확인 중..."
python3 -c "
import pyaudio
p = pyaudio.PyAudio()
print('사용 가능한 오디오 입력 디바이스:')
found = False
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f\"  [{i}] {info['name']} - {info['maxInputChannels']} channels\")
        found = True
if not found:
    print('  ⚠️  마이크가 감지되지 않았습니다.')
p.terminate()
"

# 4. Python 가상환경 생성
echo ""
echo "🐍 Python 가상환경 생성 중..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 가상환경 생성 완료"
else
    echo "✅ 가상환경이 이미 존재합니다."
fi

# 5. 가상환경 활성화 및 패키지 설치
echo ""
echo "📚 Python 패키지 설치 중..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. .env 파일 확인
echo ""
echo "⚙️  환경 설정 확인 중..."
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다."
    echo "   다음 내용으로 .env 파일을 생성하세요:"
    echo ""
    echo "APP_SERVER_URL=http://<your-app-server-ip>:8080"
    echo "WEBHOOK_ENDPOINT=/api/stt/start"
    echo "STT_BUFFER_DURATION_SEC=4.0"
    echo "GOOGLE_APPLICATION_CREDENTIALS=./secrets/stt-key.json"
    echo "LANGUAGE=ko-KR"
    echo "DEVICE_INDEX=0"
    echo ""
else
    echo "✅ .env 파일이 존재합니다."
fi

# 7. GCP 인증 키 확인
echo ""
echo "🔑 GCP 인증 키 확인 중..."
if [ -f "secrets/stt-key.json" ]; then
    echo "✅ GCP 인증 키 발견"
else
    echo "⚠️  GCP 인증 키가 없습니다. (secrets/stt-key.json)"
    echo "   GCP 인증 키를 추가하세요."
fi

# 8. 완료 메시지
echo ""
echo "========================================"
echo "✅ 설정 완료!"
echo ""
echo "다음 단계:"
echo "1. .env 파일을 설정하세요 (마이크 디바이스 인덱스 포함)"
echo "2. GCP 인증 키를 추가하세요 (secrets/stt-key.json)"
echo "3. 테스트 실행: python3 tests/test_modules.py"
echo "4. 전체 실행: python3 main.py"
echo ""

