# 🍓 라즈베리파이 배포 가이드

라즈베리파이에서 AI Supporter를 실행하는 방법입니다.

## 🚀 빠른 시작

### 1. 프로젝트 복사

```bash
# 라즈베리파이에 SSH 접속
ssh pi@<raspberry-pi-ip>

# 프로젝트 디렉토리로 이동
cd ~/AI_Supporter
```

### 2. 환경 설정

```bash
# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 시스템 패키지 설치 (PyAudio 등)
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio

# Python 패키지 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정

```bash
cp .env.example .env
nano .env
```

필수 설정:
- `APP_SERVER_URL`: 앱 서버 주소
- `DEVICE_INDEX`: 마이크 디바이스 인덱스 (아래 명령으로 확인)

```bash
# 마이크 디바이스 확인
python3 -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f\"[{i}] {info['name']}\")
p.terminate()
"
```

### 4. 실행

```bash
# 테스트 모드
python3 tests/test_modules.py

# 프로덕션 모드
python3 main.py
```

## 📝 상세 가이드

자세한 내용은 `tests/TEST_GUIDE_RASPBERRYPI.md`를 참고하세요.

