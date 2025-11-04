
import os
import pvporcupine
import wave
import struct

ACCESS_KEY = "/bCXg/NmaoITjhc/Cfao8uegDFPJW6Mo6xAGBwHODFy1JLFeDMXTzw=="
KEYWORD_PATH = "On-Air-on_en_raspberry-pi_v3_0_0.ppn"
AUDIO_DIR = "./on_air_on"  # 검사할 폴더

porcupine = pvporcupine.create(
    access_key=ACCESS_KEY,
    keyword_paths=[KEYWORD_PATH]
)

def detect_wakeword(wav_path):
    with wave.open(wav_path, "rb") as wf:
        assert wf.getframerate() == porcupine.sample_rate, "❌ Sample rate must be 16kHz"
        assert wf.getnchannels() == 1, "❌ Must be mono audio"

        num_frames = wf.getnframes()
        for i in range(0, num_frames, porcupine.frame_length):
            frame = wf.readframes(porcupine.frame_length)
            if len(frame) == 0:
                break
            pcm = struct.unpack_from("h" * porcupine.frame_length, frame)
            result = porcupine.process(pcm)
            if result >= 0:
                return True
    return False


# 폴더 내 파일 순회
for file in os.listdir(AUDIO_DIR):
    if file.endswith(".m4a"):
        path = os.path.join(AUDIO_DIR, file)
        if detect_wakeword(path):
            print(f"✅ Wakeword detected in {file}")
        else:
            print(f"❌ No wakeword in {file}")

porcupine.delete()
