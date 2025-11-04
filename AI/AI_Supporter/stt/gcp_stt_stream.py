import time
import asyncio
from google.cloud import speech
from .vad_utils import has_voice
from config import settings

class GcpStreamingStt:
    def __init__(self):
        self.language = settings.LANGUAGE
        self.rate = settings.RATE
        self.client = speech.SpeechClient()
        self._stop = False

    async def run(self, mic, broadcaster):
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.rate,
            language_code=self.language,
            enable_automatic_punctuation=True,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
        )

        last_voice_ts = time.time()

        loop = asyncio.get_running_loop()
        results_queue: asyncio.Queue = asyncio.Queue()

        def gen():
            nonlocal last_voice_ts
            while not self._stop:
                chunk = mic.read()
                if chunk is None:
                    break
                if has_voice(chunk):
                    last_voice_ts = time.time()
                yield speech.StreamingRecognizeRequest(audio_content=chunk)

        def blocking_stream():
            try:
                responses = self.client.streaming_recognize(streaming_config, gen())
                for response in responses:
                    for result in response.results:
                        txt = result.alternatives[0].transcript
                        msg_type = "final" if result.is_final else "interim"
                        asyncio.run_coroutine_threadsafe(
                            results_queue.put({"type": msg_type, "text": txt}), loop
                        )

                    # silence timeout check
                    if time.time() - last_voice_ts > settings.SILENCE_TIMEOUT_SEC:
                        asyncio.run_coroutine_threadsafe(
                            results_queue.put({"type": "info", "text": "silence_timeout"}), loop
                        )
                        break
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    results_queue.put({"type": "error", "text": str(e)}), loop
                )
            finally:
                # sentinel to end async consumer
                asyncio.run_coroutine_threadsafe(results_queue.put(None), loop)

        await loop.run_in_executor(None, blocking_stream)

        while True:
            msg = await results_queue.get()
            if msg is None:
                break
            msg_type = msg.get("type")
            txt = msg.get("text", "")
            if msg_type in ("final", "interim"):
                await broadcaster(f'{{"type":"{msg_type}","text":"{txt}"}}')
            elif msg_type in ("info", "error"):
                await broadcaster(f'{{"type":"{msg_type}","text":"{txt}"}}')

    def stop(self):
        self._stop = True
