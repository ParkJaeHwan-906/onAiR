# 🍓 라즈베리파이 테스트 가이드

라즈베리파이에서 실제 마이크로 테스트하는 방법입니다.

## 📋 사전 준비

### 1. 라즈베리파이 설정

#### A. 마이크 연결 확인
```bash
# 오디오 디바이스 확인
arecord -l

# 마이크 테스트 (Ctrl+C로 종료)
arecord -d 5 -f cd test.wav && aplay test.wav
```

#### B. 마이크 권한 확인
```bash
# 사용자가 audio 그룹에 속해있는지 확인
groups

# audio 그룹에 추가 (필요시)
sudo usermod -a -G audio $USER
# 재로그인 필요
```

### 2. 프로젝트 파일 전송

#### 방법 A: Git 사용 (권장)
```bash
# 라즈베리파이에서
cd ~
git clone <your-repo-url>
cd AI_Supporter
```

#### 방법 B: SCP 사용
```bash
# PC에서 라즈베리파이로 전송
scp -r AI_Supporter pi@<raspberry-pi-ip>:~/
```

#### 방법 C: USB/네트워크 드라이브
- USB 메모리나 네트워크 드라이브로 파일 복사

### 3. 라즈베리파이에서 의존성 설치

```bash
# 라즈베리파이에 SSH 접속
ssh pi@<raspberry-pi-ip>

# 프로젝트 디렉토리로 이동
cd ~/AI_Supporter

# Python 가상환경 생성 (권장)
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

**주의사항:**
- PyAudio는 시스템 패키지가 필요할 수 있습니다:
  ```bash
  sudo apt-get update
  sudo apt-get install portaudio19-dev python3-pyaudio
  ```

### 4. 환경 변수 설정

```bash
# .env 파일 생성
nano .env
```

`.env` 파일 내용:
```env
# 앱 서버 설정 (라즈베리파이의 IP 또는 앱 서버 IP)
APP_SERVER_URL=http://<app-server-ip>:8080
WEBHOOK_ENDPOINT=/api/stt/start

# STT 버퍼링 시간 (초)
STT_BUFFER_DURATION_SEC=4.0

# GCP 인증 (경로 확인)
GOOGLE_APPLICATION_CREDENTIALS=./secrets/stt-key.json
LANGUAGE=ko-KR

# 오디오 디바이스 (arecord -l로 확인한 인덱스)
DEVICE_INDEX=0
```

## 🧪 라즈베리파이에서 테스트

### 1. 마이크 디바이스 확인

```bash
python3 -c "
import pyaudio
p = pyaudio.PyAudio()
print('사용 가능한 오디오 입력 디바이스:')
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f\"  [{i}] {info['name']} - {info['maxInputChannels']} channels\")
p.terminate()
"
```

이 출력을 보고 `.env`의 `DEVICE_INDEX`를 설정하세요.

### 2. 개별 모듈 테스트

```bash
# 마이크 스트림 테스트
python3 tests/test_modules.py
# 메뉴에서 1번 선택

# Wakeword 감지 테스트
python3 tests/test_modules.py
# 메뉴에서 2번 선택
# "onAir"라고 말해보세요
```

### 3. 전체 시스템 테스트

#### 터미널 1: Webhook 테스트 서버 (PC 또는 라즈베리파이)
```bash
# PC에서 실행 (또는 라즈베리파이에서)
python3 tests/test_webhook_server.py
```

#### 터미널 2: WebSocket 클라이언트 (PC)
```bash
# PC에서 실행
python3 tests/test_websocket_client.py
```

#### 터미널 3: 메인 서버 (라즈베리파이)
```bash
# 라즈베리파이에서 실행
cd ~/AI_Supporter
python3 main.py
```

**테스트 순서:**
1. ✅ 서버들이 모두 시작되었는지 확인
2. ✅ "onAir"라고 말하기
3. ✅ Wakeword 감지 확인
4. ✅ Webhook 전송 확인 (터미널 1)
5. ✅ 마이크 활성화 확인
6. ✅ 3~5초 동안 말하기
7. ✅ STT 결과 확인 (터미널 2)

## 🔧 라즈베리파이 특화 설정

### 1. 오디오 시스템 설정

```bash
# ALSA 설정 확인
cat /proc/asound/cards

# 기본 오디오 카드 설정 (필요시)
sudo nano /etc/asound.conf
```

### 2. 자동 시작 설정 (systemd)

`/etc/systemd/system/ai-supporter.service` 파일 생성:

```ini
[Unit]
Description=AI Supporter STT Service
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/AI_Supporter
Environment="PATH=/home/pi/AI_Supporter/venv/bin"
ExecStart=/home/pi/AI_Supporter/venv/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

서비스 활성화:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-supporter
sudo systemctl start ai-supporter

# 상태 확인
sudo systemctl status ai-supporter
```

### 3. 네트워크 설정

라즈베리파이의 고정 IP 설정 (권장):

```bash
sudo nano /etc/dhcpcd.conf
```

추가:
```
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8
```

### 4. 방화벽 설정 (필요시)

```bash
# UFW 사용 시
sudo ufw allow 8000/tcp  # WebSocket 서버
sudo ufw allow 22/tcp    # SSH
```

## 🐛 라즈베리파이 특화 문제 해결

### 마이크가 인식되지 않음
```bash
# USB 마이크인 경우
lsusb | grep -i audio

# ALSA 재로드
sudo alsa force-reload

# 마이크 레벨 확인
alsamixer
# F4로 Capture 레벨 조정
```

### 권한 오류
```bash
# audio 그룹 확인
groups $USER

# audio 그룹 추가
sudo usermod -a -G audio $USER
# 재로그인 필요
```

### PyAudio 설치 오류
```bash
# 시스템 패키지 설치
sudo apt-get update
sudo apt-get install portaudio19-dev python3-pyaudio

# 가상환경에서 재설치
pip install --upgrade pyaudio
```

### 메모리 부족
```bash
# 스왑 파일 크기 확인
free -h

# 스왑 파일 증가 (필요시)
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# CONF_SWAPSIZE=2048 로 변경
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### TensorFlow Lite 속도 개선
```bash
# NumPy 최적화
pip install numpy --upgrade

# TensorFlow Lite 최적화 버전 사용
# (ARM용 빌드된 버전이 있는지 확인)
```

## 📊 예상 출력 (라즈베리파이)

```
🎧 STT 루프 대기 시작 (마이크 OFF)
✅ Wakeword 모델 로드 완료: .../wakeword_onair_cnn.tflite
🎧 Wakeword 감지 대기 중... (onAir)
🚀 Wakeword 감지됨! (신뢰도: 87.5%)
🚀 Wakeword 감지됨: STT 세션 시작
✅ Webhook 전송 성공: http://192.168.1.50:8080/api/stt/start
🔊 마이크 ON (활성 상태)
🎤 음성 수집 시작 (4.0초)...
   수집 중... 1.0초 / 4.0초
   수집 중... 2.0초 / 4.0초
   수집 중... 3.0초 / 4.0초
   수집 중... 4.0초 / 4.0초
✅ 음성 수집 완료 (128000 bytes)
📤 GCP STT 요청 전송 중...
📝 STT 결과: 안녕하세요 (신뢰도: 0.95)
🔇 마이크 OFF (대기 상태)
🟢 STT 세션 종료, 다시 대기 중... (마이크 OFF)
```

## ✅ 체크리스트

라즈베리파이 테스트 준비:

- [ ] 마이크 연결 및 인식 확인
- [ ] 오디오 권한 확인 (audio 그룹)
- [ ] 프로젝트 파일 전송 완료
- [ ] 의존성 설치 완료
- [ ] .env 파일 설정 완료
- [ ] 마이크 디바이스 인덱스 확인
- [ ] 네트워크 연결 확인 (앱 서버 접근 가능)
- [ ] GCP 인증 키 확인
- [ ] 개별 모듈 테스트 통과
- [ ] 전체 시스템 테스트 통과

## 🔌 원격 접속 팁

### SSH 접속
```bash
# PC에서
ssh pi@<raspberry-pi-ip>

# SSH 키 사용 (권장)
ssh-copy-id pi@<raspberry-pi-ip>
```

### VNC 접속 (GUI 필요시)
```bash
# 라즈베리파이에서
sudo apt-get install realvnc-vnc-server
sudo systemctl enable vncserver-x11-serviced
```

### 파일 전송 (SCP)
```bash
# PC → 라즈베리파이
scp file.txt pi@<raspberry-pi-ip>:~/AI_Supporter/

# 라즈베리파이 → PC
scp pi@<raspberry-pi-ip>:~/AI_Supporter/log.txt ./
```

