#!/usr/bin/env python3
"""
ALSA 레벨에서 마이크 장치 확인 스크립트
"""
import subprocess
import sys

print("=" * 60)
print("🔍 ALSA 레벨 마이크 장치 확인")
print("=" * 60)

# 1. arecord -l 실행
print("\n1. ALSA 캡처 장치 목록 (arecord -l):")
print("-" * 60)
try:
    result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, check=True)
    print(result.stdout)
    if not result.stdout.strip():
        print("  ❌ 마이크 장치가 없습니다!")
except subprocess.CalledProcessError as e:
    print(f"  ❌ 오류: {e}")
    print(f"  stderr: {e.stderr}")
except FileNotFoundError:
    print("  ❌ arecord 명령어를 찾을 수 없습니다. ALSA가 설치되어 있는지 확인하세요.")

# 2. aplay -l 실행 (참고용)
print("\n2. ALSA 재생 장치 목록 (aplay -l):")
print("-" * 60)
try:
    result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, check=True)
    print(result.stdout)
except subprocess.CalledProcessError as e:
    print(f"  ❌ 오류: {e}")
except FileNotFoundError:
    print("  ❌ aplay 명령어를 찾을 수 없습니다.")

# 3. cat /proc/asound/cards
print("\n3. ALSA 카드 정보 (/proc/asound/cards):")
print("-" * 60)
try:
    with open('/proc/asound/cards', 'r') as f:
        print(f.read())
except FileNotFoundError:
    print("  ❌ /proc/asound/cards 파일을 찾을 수 없습니다.")

# 4. sounddevice로 확인
print("\n5. sounddevice로 장치 확인:")
print("-" * 60)
try:
    import sounddevice as sd
    devices = sd.query_devices()
    print(f"  전체 장치 수: {len(devices)}")
    print("\n  입력 가능한 장치:")
    input_found = False
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            input_found = True
            print(f"    [{idx}] {dev['name']}")
            print(f"        입력 채널: {dev['max_input_channels']}")
            print(f"        샘플레이트: {dev['default_samplerate']}Hz")
            print(f"        호스트 API: {dev.get('hostapi', 'N/A')}")
    if not input_found:
        print("    ❌ 입력 가능한 장치가 없습니다!")
        print("\n  전체 장치 목록:")
        for idx, dev in enumerate(devices):
            print(f"    [{idx}] {dev['name']}")
            print(f"        입력: {dev['max_input_channels']}, 출력: {dev['max_output_channels']}")
except ImportError:
    print("  ⚠️ sounddevice가 설치되지 않았습니다.")
except Exception as e:
    print(f"  ❌ 오류: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("💡 문제 해결 방법:")
print("=" * 60)
print("1. ALSA 레벨에서 마이크가 인식되면:")
print("   - sounddevice가 ALSA를 제대로 인식하지 못하는 것일 수 있습니다.")
print("   - config/settings.py에서 DEVICE_INDEX를 직접 지정하세요.")
print("   - 또는 ALSA 장치 이름을 직접 사용하세요 (예: 'hw:0,0')")
print()
print("2. 권한 문제일 수 있습니다:")
print("   - $ sudo usermod -a -G audio $USER")
print("   - 재로그인 후 다시 시도")

