from pydub import AudioSegment
import imageio_ffmpeg
import os

# ffmpeg 경로를 pydub에 등록
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

print("✅ ffmpeg 경로:", ffmpeg_path)

# 변환 파일 설정
input_path = r"C:\Users\SSAFY\Documents\S13P31A407\mobile\app\src\main\assets\stt_test.m4a"
output_path = r"C:\Users\SSAFY\Documents\S13P31A407\mobile\app\src\main\assets\stt_test.wav"

audio = AudioSegment.from_file(input_path, format="m4a")
audio = audio.set_channels(1).set_frame_rate(16000)
audio.export(output_path, format="wav")

print("✅ 변환 완료:", output_path)
