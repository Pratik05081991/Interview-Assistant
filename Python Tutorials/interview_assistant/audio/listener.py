"""
audio/listener.py — Captures microphone audio and converts speech to text.
Supports two backends:
  - "google"  : Google Web Speech API (free, needs internet)
  - "whisper" : OpenAI Whisper (local, offline, more accurate)
"""

from __future__ import annotations
import threading
import queue
import time


class AudioListener:
    def __init__(self, config, transcript_queue: queue.Queue):
        self.config   = config
        self.out_q    = transcript_queue
        self._running = False
        self._thread: threading.Thread | None = None
        self._recognizer = None
        self._whisper_model = None

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------ #
    #  Core loop                                                           #
    # ------------------------------------------------------------------ #

    def _listen_loop(self):
        try:
            import speech_recognition as sr
        except ImportError:
            self.out_q.put("[ERROR] speech_recognition not installed. Run: pip install SpeechRecognition")
            return

        r = sr.Recognizer()
        r.pause_threshold      = self.config.PAUSE_THRESHOLD
        r.dynamic_energy_threshold = True

        # Load whisper model once if needed
        if self.config.STT_BACKEND == "whisper":
            self._load_whisper()

        mic_index = self.config.MIC_INDEX

        with sr.Microphone(device_index=mic_index) as source:
            r.adjust_for_ambient_noise(source, duration=1)
            print("[AudioListener] Listening...")

            while self._running:
                try:
                    audio = r.listen(source, timeout=5, phrase_time_limit=30)
                    threading.Thread(
                        target=self._transcribe,
                        args=(r, audio),
                        daemon=True
                    ).start()
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"[AudioListener] Listen error: {e}")
                    time.sleep(1)

    def _transcribe(self, recognizer, audio):
        try:
            if self.config.STT_BACKEND == "whisper" and self._whisper_model:
                text = self._transcribe_whisper(audio)
            else:
                text = recognizer.recognize_google(audio)

            text = text.strip()
            if len(text) > 10:          # ignore very short fragments
                print(f"[AudioListener] Heard: {text}")
                self.out_q.put(text)

        except Exception as e:
            if "UnknownValueError" not in type(e).__name__:
                print(f"[AudioListener] Transcribe error: {e}")

    def _transcribe_whisper(self, audio) -> str:
        import io, numpy as np, soundfile as sf
        wav_data = io.BytesIO(audio.get_wav_data())
        data, samplerate = sf.read(wav_data)
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = data.astype(np.float32)
        result = self._whisper_model.transcribe(data, fp16=False)
        return result["text"]

    def _load_whisper(self):
        try:
            import whisper
            print(f"[AudioListener] Loading Whisper model '{self.config.WHISPER_MODEL}'…")
            self._whisper_model = whisper.load_model(self.config.WHISPER_MODEL)
            print("[AudioListener] Whisper model ready.")
        except ImportError:
            print("[AudioListener] openai-whisper not installed. Falling back to Google STT.")
            self.config.STT_BACKEND = "google"
