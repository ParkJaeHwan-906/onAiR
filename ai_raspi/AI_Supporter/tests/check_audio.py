import wave
import sys
import struct

file_path = 'stt_buffer.wav'
try:
    w = wave.open(file_path, 'rb')
    total_frames = w.getnframes()
    print(f"파일 정보:")
    print(f"  총 프레임: {total_frames}")
    print(f"  샘플레이트: {w.getframerate()} Hz")
    print(f"  채널: {w.getnchannels()}")
    print(f"  샘플 폭: {w.getsampwidth()} bytes")
    
    # 전체 파일 읽기
    w.rewind()
    all_data = w.readframes(total_frames)
    w.close()
    
    print(f"\n오디오 데이터 분석:")
    print(f"  전체 바이트 수: {len(all_data)}")
    
    # 처음, 중간, 끝 부분 확인
    chunk_size = 1000
    
    # 처음 부분
    start_data = all_data[:chunk_size]
    non_zero_start = sum(1 for b in start_data if b != 0)
    print(f"  처음 {chunk_size}바이트 중 0이 아닌 바이트: {non_zero_start} / {chunk_size}")
    
    # 중간 부분
    mid_start = len(all_data) // 2
    mid_data = all_data[mid_start:mid_start + chunk_size]
    non_zero_mid = sum(1 for b in mid_data if b != 0)
    print(f"  중간 {chunk_size}바이트 중 0이 아닌 바이트: {non_zero_mid} / {chunk_size}")
    
    # 끝 부분
    end_data = all_data[-chunk_size:]
    non_zero_end = sum(1 for b in end_data if b != 0)
    print(f"  끝 {chunk_size}바이트 중 0이 아닌 바이트: {non_zero_end} / {chunk_size}")
    
    # 전체에서 0이 아닌 바이트 개수
    total_non_zero = sum(1 for b in all_data if b != 0)
    print(f"  전체 0이 아닌 바이트: {total_non_zero} / {len(all_data)} ({total_non_zero * 100 / len(all_data):.2f}%)")
    
    # 샘플 값 분석 (16비트 PCM)
    if len(all_data) >= 2:
        samples = [struct.unpack('<h', all_data[i:i+2])[0] for i in range(0, len(all_data)-1, 2)]
        max_abs = max(abs(s) for s in samples)
        print(f"  전체 샘플 중 최대 절댓값: {max_abs}")
        
        # 0이 아닌 샘플 위치 찾기
        non_zero_samples = [i for i, s in enumerate(samples) if s != 0]
        if non_zero_samples:
            print(f"  첫 번째 0이 아닌 샘플 위치: {non_zero_samples[0]} (약 {non_zero_samples[0] / w.getframerate():.2f}초)")
            print(f"  마지막 0이 아닌 샘플 위치: {non_zero_samples[-1]} (약 {non_zero_samples[-1] / w.getframerate():.2f}초)")
        else:
            print(f"  경고: 모든 샘플이 0입니다!")
    
    if total_non_zero == 0:
        print("\n!!! 경고: 파일이 완전히 조용합니다. 모든 데이터가 0입니다.")
        print("   원본 M4A 파일이 제대로 변환되지 않았거나, 실제로 조용한 파일일 수 있습니다.")
    elif total_non_zero < len(all_data) * 0.01:  # 1% 미만
        print("\n경고: 파일이 거의 조용합니다. 음성이 매우 작거나 손상되었을 수 있습니다.")
    else:
        print("\n오디오 데이터가 존재합니다.")
        
except Exception as e:
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

