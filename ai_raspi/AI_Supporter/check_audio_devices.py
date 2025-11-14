#!/usr/bin/env python3
"""
라즈베리파이에서 사용 가능한 오디오 장치 목록 확인 스크립트
"""
import sounddevice as sd

print("=" * 60)
print("🔍 사용 가능한 오디오 장치 목록")
print("=" * 60)

try:
    devices = sd.query_devices()
    default_device = sd.default.device
    
    # _InputOutputPair 객체 처리
    default_input_idx = None
    default_output_idx = None
    
    if hasattr(default_device, 'input'):
        default_input_idx = default_device.input
    elif hasattr(default_device, 'output'):
        default_output_idx = default_device.output
    
    if hasattr(default_device, '__getitem__'):
        try:
            if default_input_idx is None:
                default_input_idx = default_device[0]
                if hasattr(default_input_idx, 'input'):
                    default_input_idx = default_input_idx.input
            if default_output_idx is None:
                default_output_idx = default_device[1] if len(default_device) > 1 else None
                if default_output_idx and hasattr(default_output_idx, 'output'):
                    default_output_idx = default_output_idx.output
        except (TypeError, IndexError):
            pass
    
    print(f"\n기본 장치 설정:")
    print(f"  입력: {default_input_idx if default_input_idx is not None else 'None'}")
    print(f"  출력: {default_output_idx if default_output_idx is not None else 'None'}")
    print()
    
    print("전체 장치 목록:")
    print("-" * 60)
    
    input_devices = []
    
    for idx, dev in enumerate(devices):
        is_input = dev['max_input_channels'] > 0
        is_output = dev['max_output_channels'] > 0
        is_default_input = isinstance(default_input_idx, int) and idx == default_input_idx
        is_default_output = isinstance(default_output_idx, int) and idx == default_output_idx
        
        device_type = []
        if is_input:
            device_type.append("입력")
        if is_output:
            device_type.append("출력")
        
        marker = ""
        if is_default_input:
            marker += " [기본 입력]"
        if is_default_output:
            marker += " [기본 출력]"
        
        print(f"[{idx}] {dev['name']}")
        print(f"     타입: {', '.join(device_type) if device_type else '없음'}")
        print(f"     입력 채널: {dev['max_input_channels']}")
        print(f"     출력 채널: {dev['max_output_channels']}")
        print(f"     기본 샘플레이트: {dev['default_samplerate']}Hz{marker}")
        print()
        
        if is_input:
            input_devices.append((idx, dev))
    
    print("=" * 60)
    print("입력 가능한 장치 (마이크):")
    print("-" * 60)
    
    if input_devices:
        for idx, dev in input_devices:
            print(f"  [{idx}] {dev['name']} (샘플레이트: {dev['default_samplerate']}Hz)")
        
        print()
        print("=" * 60)
        print("💡 권장 설정:")
        print("=" * 60)
        if isinstance(default_input_idx, int) and default_input_idx >= 0:
            print(f"  DEVICE_INDEX = {default_input_idx}  # 기본 입력 장치")
        else:
            print(f"  DEVICE_INDEX = {input_devices[0][0]}  # 첫 번째 입력 장치")
    else:
        print("  ❌ 입력 가능한 장치가 없습니다!")
        print()
        print("  문제 해결 방법:")
        print("  1. 마이크가 연결되어 있는지 확인")
        print("  2. USB 마이크인 경우 연결 확인")
        print("  3. ALSA 설정 확인")
        print("  4. 권한 확인: $ sudo usermod -a -G audio $USER")
        
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()

