#!/usr/bin/env python3
"""
마이크 인식 진단 스크립트
라즈베리파이에서 마이크 인식 문제를 진단합니다.
"""

import sys
import subprocess

print("=" * 60)
print("🔍 마이크 인식 진단 시작")
print("=" * 60)

# 1. ALSA 장치 확인
print("\n1️⃣ ALSA 장치 확인 중...")
try:
    result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print("✅ arecord 명령 실행 성공:")
        print(result.stdout)
        if 'card' in result.stdout.lower():
            print("✅ 마이크 장치가 ALSA에서 인식됨")
        else:
            print("❌ ALSA에서 마이크 장치를 찾을 수 없음")
    else:
        print(f"❌ arecord 명령 실행 실패: {result.stderr}")
except FileNotFoundError:
    print("❌ arecord 명령을 찾을 수 없음 (alsa-utils 설치 필요)")
except Exception as e:
    print(f"❌ 오류: {e}")

# 2. sounddevice 확인
print("\n2️⃣ sounddevice 라이브러리 확인 중...")
try:
    import sounddevice as sd
    print("✅ sounddevice 라이브러리 설치됨")
    
    # 사용 가능한 장치 목록
    print("\n   사용 가능한 오디오 장치:")
    devices = sd.query_devices()
    input_devices = []
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            input_devices.append((idx, dev))
            print(f"   [{idx}] {dev['name']}")
            print(f"       입력 채널: {dev['max_input_channels']}, 샘플레이트: {dev['default_samplerate']}Hz")
    
    if not input_devices:
        print("   ❌ 입력 가능한 장치가 없음")
    else:
        print(f"   ✅ 입력 가능한 장치 {len(input_devices)}개 발견")
    
    # 기본 장치 확인
    print("\n   기본 입력 장치:")
    try:
        default = sd.default.device
        if hasattr(default, 'input'):
            default_input = default.input
        elif hasattr(default, '__getitem__'):
            default_input = default[0]
            if hasattr(default_input, 'input'):
                default_input = default_input.input
        else:
            default_input = None
        
        if default_input is not None:
            dev_info = sd.query_devices(default_input)
            print(f"   [{default_input}] {dev_info['name']}")
            print(f"       입력 채널: {dev_info['max_input_channels']}")
        else:
            print("   ⚠️ 기본 입력 장치가 설정되지 않음")
    except Exception as e:
        print(f"   ⚠️ 기본 장치 확인 실패: {e}")
    
    # 호스트 API 확인
    print("\n   호스트 API:")
    try:
        hostapis = sd.query_hostapis()
        alsa_found = False
        for api in hostapis:
            api_name = api.get('name', 'Unknown')
            print(f"   - {api_name}")
            if 'ALSA' in api_name or 'alsa' in api_name.lower():
                alsa_found = True
        
        if alsa_found:
            print("   ✅ ALSA 호스트 API 발견")
        else:
            print("   ⚠️ ALSA 호스트 API를 찾을 수 없음")
    except Exception as e:
        print(f"   ⚠️ 호스트 API 확인 실패: {e}")
        
except ImportError:
    print("❌ sounddevice 라이브러리가 설치되지 않음")
    print("   설치: pip3.10 install sounddevice==0.5.3")
except Exception as e:
    print(f"❌ 오류: {e}")

# 3. 권한 확인
print("\n3️⃣ 오디오 권한 확인 중...")
try:
    import os
    import grp
    
    user = os.getenv('USER')
    groups = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
    gid = os.getgid()
    for g in grp.getgrall():
        if g.gr_gid == gid:
            groups.append(g.gr_name)
    
    if 'audio' in groups:
        print(f"✅ 사용자 '{user}'가 audio 그룹에 속함")
    else:
        print(f"❌ 사용자 '{user}'가 audio 그룹에 속하지 않음")
        print("   해결: sudo usermod -a -G audio $USER")
        print("   재로그인 필요")
except Exception as e:
    print(f"⚠️ 권한 확인 실패: {e}")

# 4. 다른 프로세스가 마이크를 점유하고 있는지 확인
print("\n4️⃣ 마이크 점유 프로세스 확인 중...")
try:
    result = subprocess.run(['lsof', '/dev/snd/*'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0 and result.stdout.strip():
        print("⚠️ 마이크를 사용 중인 프로세스:")
        print(result.stdout)
    else:
        print("✅ 마이크를 점유하는 프로세스 없음")
except FileNotFoundError:
    print("⚠️ lsof 명령을 찾을 수 없음 (무시 가능)")
except Exception as e:
    print(f"⚠️ 확인 실패: {e}")

# 5. 실제 마이크 테스트
print("\n5️⃣ 마이크 테스트 (1초 녹음 시도)...")
try:
    import sounddevice as sd
    import numpy as np
    
    sample_rate = 16000
    duration = 1.0
    
    print(f"   샘플레이트: {sample_rate}Hz, 길이: {duration}초")
    print("   녹음 중...")
    
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    
    # RMS 값 확인 (음성이 있는지)
    rms = np.sqrt(np.mean(recording.astype(np.float64) ** 2))
    print(f"   ✅ 녹음 성공 (RMS: {rms:.2f})")
    
    if rms < 100:
        print("   ⚠️ 경고: RMS 값이 매우 낮음 (마이크가 음성을 받지 못할 수 있음)")
    else:
        print("   ✅ 마이크가 정상적으로 작동 중")
        
except Exception as e:
    print(f"   ❌ 마이크 테스트 실패: {e}")
    print(f"   오류 타입: {type(e).__name__}")

print("\n" + "=" * 60)
print("✅ 진단 완료")
print("=" * 60)

