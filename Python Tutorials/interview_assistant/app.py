"""
app.py — Orchestrates all modules: UI, audio listener, AI engine.
"""

import threading
import queue
import sys
from ui.overlay import OverlayWindow
from audio.listener import AudioListener
from ai.engine import AIEngine
from config import Config


class InterviewAssistantApp:
    def __init__(self):
        self.config = Config()
        self.message_queue = queue.Queue()   # audio → transcripts
        self.answer_queue  = queue.Queue()   # AI  → answers

        # Core components
        self.ai_engine     = AIEngine(self.config)
        self.audio_listener = AudioListener(self.config, self.message_queue)
        self.ui            = OverlayWindow(self.config, self.answer_queue)

        # Wire callbacks
        self.ui.on_manual_question = self._handle_question
        self.ui.on_toggle_listen   = self._toggle_listening
        self.ui.on_clear           = self._clear_history
        self.ui.on_settings_save   = self._reload_config

        self._listening = False
        self._transcript_thread = None

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def run(self):
        """Start the application (blocking call — runs the Tk main loop)."""
        self._start_transcript_worker()
        self.ui.run()          # blocks until window is closed
        self._shutdown()

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _start_transcript_worker(self):
        """Background thread: picks up transcripts and calls AI."""
        self._transcript_thread = threading.Thread(
            target=self._transcript_loop, daemon=True
        )
        self._transcript_thread.start()

    def _transcript_loop(self):
        while True:
            try:
                text = self.message_queue.get(timeout=0.5)
                if text == "__STOP__":
                    break
                self._handle_question(text, source="mic")
            except queue.Empty:
                continue

    def _handle_question(self, question: str, source: str = "manual"):
        """Send question to AI and push answer to UI queue."""
        if not question.strip():
            return

        # Show typing indicator in UI
        self.ui.show_thinking(question, source)

        def _worker():
            answer = self.ai_engine.get_answer(question)
            self.answer_queue.put({"question": question, "answer": answer, "source": source})

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_listening(self, enabled: bool):
        if enabled:
            self.audio_listener.start()
            self._listening = True
        else:
            self.audio_listener.stop()
            self._listening = False

    def _clear_history(self):
        self.ai_engine.clear_history()

    def _reload_config(self, new_config: dict):
        self.config.update(new_config)
        self.ai_engine.reload(self.config)

    def _shutdown(self):
        self.audio_listener.stop()
        self.message_queue.put("__STOP__")
