import sounddevice as sd
import numpy as np
from wakeup import WakewordDetector

detector = WakewordDetector("wakeword_onair_mfcc_fp16.tflite")
detector.start()

def callback(indata, frames, time_info, status):
    detector.process_audio_chunk(indata)

with sd.InputStream(
    channels=1,
    samplerate=16000,
    blocksize=512,
    dtype='float32',
    callback=callback
):
    print("말해보세요: onair")
    while True:
        if detector.wait_for_wakeword(timeout=0.5):
            print("Detected!")
