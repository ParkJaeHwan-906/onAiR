import wave
import struct
import sys

file_path = 'stt_buffer.wav'
try:
    w = wave.open(file_path, 'rb')
    total_frames = w.getnframes()
    sample_rate = w.getframerate()
    
    print(f"파일 정보:")
    print(f"  총 프레임: {total_frames} ({total_frames / sample_rate:.2f}초)")
    print(f"  샘플레이트: {sample_rate} Hz")
    
    # 전체 파일 읽기
    w.rewind()
    all_data = w.readframes(total_frames)
    w.close()
    
    # 16비트 PCM 샘플로 변환
    samples = [struct.unpack('<h', all_data[i:i+2])[0] for i in range(0, len(all_data)-1, 2)]
    total_samples = len(samples)
    
    print(f"\n오디오 레벨 분석:")
    print(f"  총 샘플 수: {total_samples}")
    
    # 시간별로 구간을 나눠서 분석 (0.5초씩)
    segment_duration = 0.5  # 0.5초 구간
    segment_samples = int(sample_rate * segment_duration)
    
    print(f"\n구간별 오디오 레벨 분석 (0.5초 구간):")
    print(f"{'구간':<10} {'시간':<10} {'최대 절댓값':<15} {'평균 절댓값':<15} {'RMS':<15}")
    print("-" * 70)
    
    for i in range(0, total_samples, segment_samples):
        segment = samples[i:i+segment_samples]
        if not segment:
            break
            
        time_start = i / sample_rate
        time_end = min((i + len(segment)) / sample_rate, total_samples / sample_rate)
        
        # 최대 절댓값
        max_abs = max(abs(s) for s in segment) if segment else 0
        
        # 평균 절댓값
        avg_abs = sum(abs(s) for s in segment) / len(segment) if segment else 0
        
        # RMS (Root Mean Square)
        rms = (sum(s*s for s in segment) / len(segment))**0.5 if segment else 0
        
        segment_num = i // segment_samples + 1
        print(f"{segment_num:<10} {time_start:.2f}-{time_end:.2f}s   {max_abs:<15} {avg_abs:<15.2f} {rms:<15.2f}")
    
    # 전체 파일 통계
    max_overall = max(abs(s) for s in samples)
    avg_overall = sum(abs(s) for s in samples) / len(samples)
    rms_overall = (sum(s*s for s in samples) / len(samples))**0.5
    
    print(f"\n전체 통계:")
    print(f"  최대 절댓값: {max_overall}")
    print(f"  평균 절댓값: {avg_overall:.2f}")
    print(f"  RMS: {rms_overall:.2f}")
    
    # 처음 1초와 나머지 비교
    first_second_samples = int(sample_rate * 1.0)
    first_second = samples[:first_second_samples]
    rest = samples[first_second_samples:]
    
    if first_second and rest:
        max_first = max(abs(s) for s in first_second)
        max_rest = max(abs(s) for s in rest)
        avg_first = sum(abs(s) for s in first_second) / len(first_second)
        avg_rest = sum(abs(s) for s in rest) / len(rest)
        
        print(f"\n처음 1초 vs 나머지 비교:")
        print(f"  처음 1초 최대 절댓값: {max_first}")
        print(f"  나머지 최대 절댓값: {max_rest}")
        print(f"  처음 1초 평균 절댓값: {avg_first:.2f}")
        print(f"  나머지 평균 절댓값: {avg_rest:.2f}")
        
        if max_first < max_rest * 0.5:
            print(f"\n⚠️ 경고: 처음 1초의 볼륨이 나머지보다 {max_rest/max_first:.1f}배 작습니다!")
            print(f"   이로 인해 'AI 서포터' 부분이 인식되지 않았을 수 있습니다.")
        else:
            print(f"\n✅ 처음 1초와 나머지의 볼륨 차이가 크지 않습니다.")
    
except Exception as e:
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

